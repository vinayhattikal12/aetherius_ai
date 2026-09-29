from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.database import get_db
from backend.app.schemas.model_registry import (
    ModelResponse,
    CompatibilityResult,
    ModelPackageResponse,
    ModelCreate,
    HuggingFaceModelCard,
    HuggingFaceDatasetCard,
    ModelUpgradeSuggestion,
    SmartSwapRequest,
    ModelInstallProgress,
)
from backend.app.models.model_registry import ModelRegistry, ModelPackage
from backend.app.services.hardware_detector import HardwareDetector
from backend.app.services.model_registry_service import ModelRegistryService
from backend.app.services.compatibility_engine import ModelCompatibilityEngine
from backend.app.services.huggingface_service import HuggingFaceHubService
from backend.app.services.model_installation_service import model_installation_manager

router = APIRouter()


@router.get("/", response_model=List[ModelResponse])
async def list_models(
    evaluate_compatibility: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """List all registered models with optional hardware compatibility analysis."""
    profile = HardwareDetector.get_hardware_profile() if evaluate_compatibility else None
    return await ModelRegistryService.get_models(db, profile=profile)


@router.get("/packages", response_model=List[ModelPackageResponse])
async def list_model_packages(
    db: AsyncSession = Depends(get_db)
):
    """List recommended model packages."""
    packages = await ModelRegistryService.get_packages(db)
    all_models = await ModelRegistryService.get_models(db)
    models_by_name = {m.name: m for m in all_models}
    
    result = []
    for pkg in packages:
        pkg_resp = ModelPackageResponse.model_validate(pkg)
        pkg_resp.models = [models_by_name[mid] for mid in pkg.recommended_model_ids if mid in models_by_name]
        result.append(pkg_resp)
    return result


@router.get("/install/active", response_model=List[ModelInstallProgress])
async def get_active_installs():
    """Get list of all currently downloading and installing models."""
    return model_installation_manager.get_all_active_installs()


@router.get("/install/status/{model_identifier:path}", response_model=Optional[ModelInstallProgress])
async def get_install_status(model_identifier: str):
    """Get current progress state for a specific model installation."""
    return model_installation_manager.get_progress(model_identifier)


@router.get("/install/progress/{model_identifier:path}")
async def stream_install_progress(model_identifier: str):
    """Server-Sent Events (SSE) stream for real-time download and install progress."""
    return StreamingResponse(
        model_installation_manager.subscribe_progress(model_identifier),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/huggingface/trending", response_model=List[HuggingFaceModelCard])
async def get_huggingface_trending_models(
    category: Optional[str] = Query(None, description="Category filter (Coding, Reasoning, Fast, Image Generation, General)"),
    limit: int = Query(15, ge=1, le=50),
):
    """Fetch live trending open-source models from Hugging Face Hub evaluated against local PC hardware."""
    profile = HardwareDetector.get_hardware_profile()
    return await HuggingFaceHubService.fetch_trending_models(category=category, profile=profile, limit=limit)


@router.get("/huggingface/search", response_model=List[HuggingFaceModelCard])
async def search_huggingface_models(
    q: str = Query(..., description="Search query e.g. 'qwen 7b', 'deepseek', 'flux'"),
    limit: int = Query(12, ge=1, le=30),
):
    """Search for models on Hugging Face Hub with real-time hardware sizing analysis."""
    profile = HardwareDetector.get_hardware_profile()
    return await HuggingFaceHubService.search_models(query=q, profile=profile, limit=limit)


@router.get("/huggingface/datasets", response_model=List[HuggingFaceDatasetCard])
async def search_huggingface_datasets(
    q: Optional[str] = Query(None, description="Search query or category for datasets"),
    limit: int = Query(12, ge=1, le=30),
):
    """Fetch and discover open-source Hugging Face datasets."""
    return await HuggingFaceHubService.fetch_popular_datasets(query=q, limit=limit)


@router.get("/daily-feed")
async def get_daily_open_source_feed():
    """Returns the daily updated open-source models, releases, and datasets feed."""
    profile = HardwareDetector.get_hardware_profile()
    return await HuggingFaceHubService.get_daily_feed(profile=profile)


@router.post("/sync-daily")
async def sync_daily_open_source_models(
    db: AsyncSession = Depends(get_db)
):
    """Force an immediate live synchronization with Hugging Face Hub and Ollama for newly released models/versions."""
    profile = HardwareDetector.get_hardware_profile()
    # Also ensure default models and packages in DB are in sync
    await ModelRegistryService.seed_default_models(db)
    return await HuggingFaceHubService.sync_daily_catalog(profile=profile)


@router.get("/upgrade-suggestions", response_model=List[ModelUpgradeSuggestion])
async def get_model_upgrade_suggestions(
    db: AsyncSession = Depends(get_db)
):
    """Returns AI upgrade recommendations based on newly published open-source models."""
    profile = HardwareDetector.get_hardware_profile()
    all_models = await ModelRegistryService.get_models(db)
    installed_models = [
        {"name": m.name, "category": m.category, "parameters_b": m.parameters_b}
        for m in all_models
        if m.is_installed and m.is_local
    ]
    return HuggingFaceHubService.get_model_upgrade_suggestions(installed_models, profile)


@router.post("/evaluate-compatibility", response_model=CompatibilityResult)
async def evaluate_model_compatibility(
    model: ModelCreate
):
    """Evaluate compatibility of any model against current hardware."""
    profile = HardwareDetector.get_hardware_profile()
    return ModelCompatibilityEngine.evaluate(profile, model)


@router.post("/huggingface/install", response_model=ModelInstallProgress)
async def install_huggingface_model(
    repo_id: str = Query(..., description="Hugging Face repo ID e.g. Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"),
    quantization: str = Query("Q4_K_M"),
    db: AsyncSession = Depends(get_db)
):
    """1-Click Install of any Hugging Face model directly into local runtime with live progress."""
    clean_display = repo_id.split("/")[-1].replace("-GGUF", "").replace("_GGUF", "").replace("-", " ").title()
    progress = await model_installation_manager.start_install(
        model_id_or_name=f"hf.co/{repo_id}",
        display_name=clean_display,
        repo_id=repo_id,
        quantization=quantization,
    )
    return progress


@router.post("/smart-swap", response_model=ModelInstallProgress)
async def smart_swap_model(
    req: SmartSwapRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    1-Click Smart Swap:
    Deletes older model weights to free up disk storage, then installs the superior Hugging Face model.
    """
    from backend.app.services.providers.model_manager import model_manager

    # 1. Locate and uninstall old model
    old_res = await db.execute(
        select(ModelRegistry).where((ModelRegistry.id == req.old_model_id) | (ModelRegistry.name == req.old_model_id))
    )
    old_model = old_res.scalars().first()
    if old_model and old_model.provider == "ollama":
        try:
            if await model_manager.ollama.is_available():
                await model_manager.delete_model(old_model.name)
        except Exception:
            pass
        old_model.is_installed = False
        await db.commit()

    # 2. Start installation of the new Hugging Face model
    return await install_huggingface_model(repo_id=req.new_repo_id, quantization=req.quantization, db=db)


@router.post("/{model_id}/install", response_model=ModelInstallProgress)
async def install_model(
    model_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Trigger model installation with real-time progress tracking."""
    result = await db.execute(
        select(ModelRegistry).where(
            (ModelRegistry.id == model_id)
            | (ModelRegistry.name == model_id)
            | (ModelRegistry.name == f"hf.co/{model_id}")
        )
    )
    model = result.scalars().first()
    display_name = model.display_name if model else model_id
    repo_id = model.name.replace("hf.co/", "") if model and model.name.startswith("hf.co/") else (model_id if "/" in model_id else None)

    progress = await model_installation_manager.start_install(
        model_id_or_name=model.name if model else model_id,
        display_name=display_name,
        repo_id=repo_id,
        quantization=model.quantization if model else "Q4_K_M",
    )
    return progress


@router.post("/{model_id}/uninstall", response_model=ModelResponse)
async def uninstall_model(
    model_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Uninstall model and delete from Ollama local storage."""
    from backend.app.services.providers.model_manager import model_manager

    result = await db.execute(
        select(ModelRegistry).where(
            (ModelRegistry.id == model_id)
            | (ModelRegistry.name == model_id)
            | (ModelRegistry.name == f"hf.co/{model_id}")
        )
    )
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if model.provider == "ollama":
        try:
            if await model_manager.ollama.is_available():
                await model_manager.delete_model(model.name)
        except Exception:
            pass

    model.is_installed = False
    await db.commit()
    await db.refresh(model)
    
    profile = HardwareDetector.get_hardware_profile()
    resp = ModelResponse.model_validate(model)
    resp.compatibility = ModelCompatibilityEngine.evaluate(profile, model)
    return resp


@router.post("/{model_id}/toggle-installed", response_model=ModelResponse)
async def toggle_model_installed(
    model_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Toggle actual installation status of a model, pulling or deleting from Ollama."""
    from backend.app.services.providers.model_manager import model_manager

    result = await db.execute(
        select(ModelRegistry).where(
            (ModelRegistry.id == model_id)
            | (ModelRegistry.name == model_id)
            | (ModelRegistry.name == f"hf.co/{model_id}")
        )
    )
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if model.is_installed:
        if model.provider == "ollama":
            try:
                if await model_manager.ollama.is_available():
                    await model_manager.delete_model(model.name)
            except Exception:
                pass
        model.is_installed = False
    else:
        if model.provider == "ollama":
            try:
                if await model_manager.ollama.is_available():
                    import asyncio
                    asyncio.create_task(model_manager.pull_model(model.name))
            except Exception:
                pass
        model.is_installed = True

    await db.commit()
    await db.refresh(model)
    
    profile = HardwareDetector.get_hardware_profile()
    resp = ModelResponse.model_validate(model)
    resp.compatibility = ModelCompatibilityEngine.evaluate(profile, model)
    return resp
