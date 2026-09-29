from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.schemas.system import HardwareProfile, SystemProfileResponse
from backend.app.services.hardware_detector import HardwareDetector
from backend.app.models.system_profile import SystemProfile

router = APIRouter()


@router.get("/detect", response_model=HardwareProfile)
async def detect_system():
    """Detect current real-time hardware specifications and compute tier."""
    return HardwareDetector.get_hardware_profile()


@router.post("/save-profile", response_model=SystemProfileResponse)
async def save_profile(
    db: AsyncSession = Depends(get_db)
):
    """Detect and persist the system profile in PostgreSQL."""
    profile = HardwareDetector.get_hardware_profile()
    
    db_profile = SystemProfile(
        os_name=profile.os,
        os_release=profile.os_release,
        architecture=profile.architecture,
        cpu_model=profile.cpu.model,
        cpu_physical_cores=profile.cpu.physical_cores,
        cpu_logical_cores=profile.cpu.logical_cores,
        ram_total_gb=profile.ram.total_gb,
        ram_available_gb=profile.ram.available_gb,
        gpu_models=[g.model_dump() for g in profile.gpu],
        vram_total_gb=profile.vram_gb,
        storage_total_gb=profile.storage.total_gb,
        storage_free_gb=profile.storage.free_gb,
        accelerators=profile.accelerators,
        compute_tier=profile.compute_tier,
        raw_telemetry=profile.model_dump(mode="json")
    )
    db.add(db_profile)
    await db.commit()
    await db.refresh(db_profile)

    return SystemProfileResponse(
        id=db_profile.id,
        profile=profile,
        status="saved"
    )
