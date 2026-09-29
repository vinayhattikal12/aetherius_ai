from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.model_registry import ModelRegistry, ModelPackage
from backend.app.schemas.system import HardwareProfile
from backend.app.schemas.model_registry import CompatibilityResult, ModelResponse
from backend.app.services.compatibility_engine import ModelCompatibilityEngine
from backend.app.core.logging import logger

DEFAULT_MODELS = [
    {
        "name": "llama3.2:3b",
        "display_name": "Llama 3.2 3B Instruct",
        "provider": "ollama",
        "model_family": "llama",
        "parameters_b": 3.2,
        "quantization": "Q4_K_M",
        "context_size": 8192,
        "min_ram_gb": 6.0,
        "min_vram_gb": 3.0,
        "recommended_vram_gb": 4.0,
        "cpu_compatible": True,
        "gpu_compatible": True,
        "vision_capable": False,
        "coding_capable": True,
        "reasoning_capable": True,
        "tool_calling_capable": True,
        "embedding_capable": False,
        "category": "Fast",
        "description": "Ultra-fast, efficient small language model for quick everyday queries and lightweight laptops.",
        "is_local": True,
        "is_installed": False,
        "is_recommended": True,
    },
    {
        "name": "qwen2.5-coder:7b",
        "display_name": "Qwen 2.5 Coder 7B",
        "provider": "ollama",
        "model_family": "qwen",
        "parameters_b": 7.6,
        "quantization": "Q4_K_M",
        "context_size": 16384,
        "min_ram_gb": 10.0,
        "min_vram_gb": 6.0,
        "recommended_vram_gb": 8.0,
        "cpu_compatible": True,
        "gpu_compatible": True,
        "vision_capable": False,
        "coding_capable": True,
        "reasoning_capable": True,
        "tool_calling_capable": True,
        "embedding_capable": False,
        "category": "Coding",
        "description": "State-of-the-art coding and agent model. Ideal for software development, debugging, and file manipulation.",
        "is_local": True,
        "is_installed": False,
        "is_recommended": True,
    },
    {
        "name": "deepseek-r1:8b",
        "display_name": "DeepSeek R1 8B Reasoning",
        "provider": "ollama",
        "model_family": "deepseek",
        "parameters_b": 8.0,
        "quantization": "Q4_K_M",
        "context_size": 8192,
        "min_ram_gb": 12.0,
        "min_vram_gb": 6.0,
        "recommended_vram_gb": 8.0,
        "cpu_compatible": True,
        "gpu_compatible": True,
        "vision_capable": False,
        "coding_capable": True,
        "reasoning_capable": True,
        "tool_calling_capable": True,
        "embedding_capable": False,
        "category": "Reasoning",
        "description": "Powerful chain-of-thought reasoning model for complex math, science, and multi-step logical tasks.",
        "is_local": True,
        "is_installed": False,
        "is_recommended": True,
    },
    {
        "name": "mistral:7b",
        "display_name": "Mistral 7B Instruct v0.3",
        "provider": "ollama",
        "model_family": "mistral",
        "parameters_b": 7.2,
        "quantization": "Q4_K_M",
        "context_size": 8192,
        "min_ram_gb": 10.0,
        "min_vram_gb": 6.0,
        "recommended_vram_gb": 8.0,
        "cpu_compatible": True,
        "gpu_compatible": True,
        "vision_capable": False,
        "coding_capable": True,
        "reasoning_capable": True,
        "tool_calling_capable": True,
        "embedding_capable": False,
        "category": "General",
        "description": "Balanced, versatile general-purpose instruction model for all workspace tasks.",
        "is_local": True,
        "is_installed": False,
        "is_recommended": True,
    },
    {
        "name": "nomic-embed-text",
        "display_name": "Nomic Embed Text v1.5",
        "provider": "ollama",
        "model_family": "nomic",
        "parameters_b": 0.14,
        "quantization": "Q8_0",
        "context_size": 2048,
        "min_ram_gb": 2.0,
        "min_vram_gb": 0.5,
        "recommended_vram_gb": 1.0,
        "cpu_compatible": True,
        "gpu_compatible": True,
        "vision_capable": False,
        "coding_capable": False,
        "reasoning_capable": False,
        "tool_calling_capable": False,
        "embedding_capable": True,
        "category": "Embedding",
        "description": "High-performance embedding model for PostgreSQL pgvector semantic retrieval and RAG knowledge bases.",
        "is_local": True,
        "is_installed": False,
        "is_recommended": True,
    },
    {
        "name": "claude-3-7-sonnet",
        "display_name": "Claude 3.7 Sonnet (Cloud)",
        "provider": "anthropic",
        "model_family": "claude",
        "parameters_b": 0.0,
        "quantization": "Cloud",
        "context_size": 200000,
        "min_ram_gb": 1.0,
        "min_vram_gb": 0.0,
        "recommended_vram_gb": 0.0,
        "cpu_compatible": True,
        "gpu_compatible": True,
        "vision_capable": True,
        "coding_capable": True,
        "reasoning_capable": True,
        "tool_calling_capable": True,
        "embedding_capable": False,
        "category": "Reasoning",
        "description": "Leading cloud intelligence with hybrid reasoning, multimodal vision, and deep code comprehension.",
        "is_local": False,
        "is_installed": True,
        "is_recommended": True,
    }
]

DEFAULT_PACKAGES = [
    {
        "name": "General AI Package",
        "slug": "general-package",
        "description": "A well-balanced foundation for everyday productivity, reading, summaries, and chat.",
        "target_audience": "General Users, Professionals, Students",
        "recommended_model_ids": ["llama3.2:3b", "nomic-embed-text"],
        "estimated_storage_gb": 3.0,
        "required_ram_gb": 8.0,
    },
    {
        "name": "Developer Package",
        "slug": "developer-package",
        "description": "Specialized for full-stack programming, automated refactoring, and AI agent workflows.",
        "target_audience": "Developers, Software Engineers, DevOps",
        "recommended_model_ids": ["qwen2.5-coder:7b", "deepseek-r1:8b", "nomic-embed-text"],
        "estimated_storage_gb": 10.5,
        "required_ram_gb": 16.0,
    },
    {
        "name": "Student & Research Package",
        "slug": "student-package",
        "description": "Optimized for document reading, thesis study, quiz generation, and deep reasoning.",
        "target_audience": "Students, Academics, Researchers",
        "recommended_model_ids": ["llama3.2:3b", "deepseek-r1:8b", "nomic-embed-text"],
        "estimated_storage_gb": 7.5,
        "required_ram_gb": 12.0,
    },
    {
        "name": "Enterprise & Cloud Package",
        "slug": "enterprise-package",
        "description": "Full-spectrum intelligence combining local private privacy models with high-power cloud APIs.",
        "target_audience": "Companies, Finance, HR, Executive Teams",
        "recommended_model_ids": ["mistral:7b", "claude-3-7-sonnet", "nomic-embed-text"],
        "estimated_storage_gb": 5.0,
        "required_ram_gb": 16.0,
    }
]


class ModelRegistryService:
    @staticmethod
    async def seed_default_models(db: AsyncSession) -> None:
        """Seed default model registry and packages if empty."""
        result = await db.execute(select(ModelRegistry))
        existing = result.scalars().all()
        if not existing:
            for m_data in DEFAULT_MODELS:
                model = ModelRegistry(**m_data)
                db.add(model)
            
            for p_data in DEFAULT_PACKAGES:
                package = ModelPackage(**p_data)
                db.add(package)
            
            await db.commit()
            logger.info("Default AI models and model packages seeded into PostgreSQL.")

    @staticmethod
    async def get_models(db: AsyncSession, profile: Optional[HardwareProfile] = None) -> List[ModelResponse]:
        from backend.app.services.providers.model_manager import model_manager
        installed_tags = []
        try:
            installed_tags = await model_manager.ollama.get_installed_tags()
        except Exception:
            pass

        result = await db.execute(select(ModelRegistry))
        models = list(result.scalars().all())

        # Auto-register newly discovered installed Ollama models
        existing_names = {m.name for m in models}
        for tag in installed_tags:
            tag_clean = tag.strip()
            # If tag not exact match, or base not found
            if tag_clean not in existing_names and not any(tag_clean == m.name or (":" in tag_clean and tag_clean.split(":")[0] == m.name.split(":")[0]) for m in models):
                base_name = tag_clean.split(":")[0]
                is_embedding = "embed" in tag_clean.lower()
                clean_display = tag_clean.replace(":", " ").replace("-", " ").title()
                new_model = ModelRegistry(
                    name=tag_clean,
                    display_name=f"{clean_display} (Local)",
                    provider="ollama",
                    model_family=base_name,
                    parameters_b=14.0 if "14b" in tag_clean else (8.0 if "8b" in tag_clean else (7.0 if "7b" in tag_clean else (3.0 if "3b" in tag_clean else 1.5))),
                    quantization="Q4_K_M",
                    context_size=16384 if "coder" in tag_clean else 8192,
                    min_ram_gb=16.0 if "14b" in tag_clean else (12.0 if "8b" in tag_clean else (8.0 if "7b" in tag_clean else 4.0)),
                    min_vram_gb=8.0 if "14b" in tag_clean else (6.0 if "8b" in tag_clean else (4.0 if "7b" in tag_clean else 2.0)),
                    recommended_vram_gb=10.0 if "14b" in tag_clean else (8.0 if "8b" in tag_clean else 6.0),
                    cpu_compatible=True,
                    gpu_compatible=True,
                    vision_capable="vision" in tag_clean or "vl" in tag_clean or "llava" in tag_clean,
                    coding_capable="coder" in tag_clean or "code" in tag_clean,
                    reasoning_capable="r1" in tag_clean or "reason" in tag_clean or "deepseek" in tag_clean,
                    tool_calling_capable=not is_embedding,
                    embedding_capable=is_embedding,
                    category="Embedding" if is_embedding else ("Coding" if "coder" in tag_clean else ("Reasoning" if "r1" in tag_clean else "General")),
                    description=f"Auto-detected locally installed Ollama model ({tag_clean}).",
                    is_local=True,
                    is_installed=True,
                    is_recommended=True
                )
                db.add(new_model)
                try:
                    await db.commit()
                    await db.refresh(new_model)
                    models.append(new_model)
                    existing_names.add(tag_clean)
                except Exception:
                    await db.rollback()
        
        responses: List[ModelResponse] = []
        for m in models:
            # If Ollama is available, keep is_installed synchronized with actual disk tags
            if m.provider == "ollama" and installed_tags:
                tag_matches = any(t == m.name or t.startswith(m.name.split(':')[0]) for t in installed_tags)
                if m.is_installed != tag_matches:
                    m.is_installed = tag_matches
                    try:
                        await db.commit()
                    except Exception:
                        pass

            compat = None
            if profile:
                compat = ModelCompatibilityEngine.evaluate(profile, m)
            
            resp = ModelResponse.model_validate(m)
            resp.compatibility = compat
            responses.append(resp)
        
        return responses

    @staticmethod
    async def get_packages(db: AsyncSession) -> List[ModelPackage]:
        result = await db.execute(select(ModelPackage))
        return result.scalars().all()
