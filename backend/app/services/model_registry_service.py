import os
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
        "name": "qwen2.5-coder:1.5b",
        "display_name": "Qwen 2.5 Coder 1.5B (Edge)",
        "provider": "ollama",
        "model_family": "qwen",
        "parameters_b": 1.5,
        "quantization": "Q4_K_M",
        "context_size": 8192,
        "min_ram_gb": 4.0,
        "min_vram_gb": 1.5,
        "recommended_vram_gb": 2.0,
        "cpu_compatible": True,
        "gpu_compatible": True,
        "vision_capable": False,
        "coding_capable": True,
        "reasoning_capable": False,
        "tool_calling_capable": True,
        "embedding_capable": False,
        "category": "Fast",
        "description": "Ultra-lightweight inline code generator and auto-completer designed for background IDE tasks.",
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
        "name": "qwen2.5-coder:14b",
        "display_name": "Qwen 2.5 Coder 14B (Heavyweight)",
        "provider": "ollama",
        "model_family": "qwen",
        "parameters_b": 14.7,
        "quantization": "Q4_K_M",
        "context_size": 16384,
        "min_ram_gb": 16.0,
        "min_vram_gb": 10.0,
        "recommended_vram_gb": 12.0,
        "cpu_compatible": True,
        "gpu_compatible": True,
        "vision_capable": False,
        "coding_capable": True,
        "reasoning_capable": True,
        "tool_calling_capable": True,
        "embedding_capable": False,
        "category": "Coding",
        "description": "Enterprise-grade high-precision coding model with deep repo comprehension and architectural refactoring.",
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
        "name": "Full-Stack Developer & Agent Suite",
        "slug": "developer-suite",
        "description": "Production-grade coding, automatic debugging, tool calling, unit test generation, and pgvector RAG.",
        "target_audience": "Software Engineers, Full-Stack Developers, DevOps & AI Engineers",
        "recommended_model_ids": ["qwen2.5-coder:7b", "deepseek-r1:8b", "nomic-embed-text"],
        "estimated_storage_gb": 10.5,
        "required_ram_gb": 16.0,
    },
    {
        "name": "Autonomous Research & Deep Reasoning Suite",
        "slug": "research-reasoning-suite",
        "description": "Chain-of-thought mathematical proofs, deep logical analysis, thesis synthesis, and fast drafting.",
        "target_audience": "Researchers, Academics, Analysts, Data Scientists",
        "recommended_model_ids": ["deepseek-r1:8b", "llama3.2:3b", "nomic-embed-text"],
        "estimated_storage_gb": 8.5,
        "required_ram_gb": 12.0,
    },
    {
        "name": "Lightweight Laptop AI Starter Pack",
        "slug": "starter-pack",
        "description": "Ultra-fast response times and minimal battery consumption for laptops, everyday writing, and quick coding.",
        "target_audience": "Students, Everyday Users, Mobile & Laptop Professionals",
        "recommended_model_ids": ["llama3.2:3b", "qwen2.5-coder:1.5b", "nomic-embed-text"],
        "estimated_storage_gb": 4.5,
        "required_ram_gb": 8.0,
    },
    {
        "name": "Data Science, Analytics & SQL Suite",
        "slug": "data-science-suite",
        "description": "Specialized for tabular datasets, SQL query optimization, Python pandas scripting, and statistical summaries.",
        "target_audience": "Data Analysts, BI Engineers, Quantitative Researchers",
        "recommended_model_ids": ["qwen2.5-coder:7b", "deepseek-r1:8b", "nomic-embed-text"],
        "estimated_storage_gb": 10.0,
        "required_ram_gb": 16.0,
    },
    {
        "name": "Heavyweight Workstation Engineering Pack",
        "slug": "workstation-engineering-pack",
        "description": "Maximum accuracy 14B parameter coding powerhouse paired with DeepSeek R1 reasoning for desktop workstations.",
        "target_audience": "Senior Architects, Desktop Workstations, 32GB+ RAM Systems",
        "recommended_model_ids": ["qwen2.5-coder:14b", "deepseek-r1:8b", "nomic-embed-text"],
        "estimated_storage_gb": 18.5,
        "required_ram_gb": 24.0,
    },
    {
        "name": "Multimodal Vision & Realtime Suite",
        "slug": "multimodal-vision-suite",
        "description": "High-speed document parsing, image analysis, UI design code generation, and semantic vector indexing.",
        "target_audience": "UI/UX Designers, Product Managers, Content Creators",
        "recommended_model_ids": ["llama3.2:3b", "qwen2.5-coder:7b", "nomic-embed-text"],
        "estimated_storage_gb": 9.0,
        "required_ram_gb": 16.0,
    },
    {
        "name": "Enterprise Hybrid Cloud & Local Privacy Suite",
        "slug": "enterprise-privacy-suite",
        "description": "100% offline local privacy for proprietary docs combined with Claude 3.7 Sonnet cloud scale when needed.",
        "target_audience": "Enterprises, Legal, Finance & Security-conscious Organizations",
        "recommended_model_ids": ["llama3.2:3b", "claude-3-7-sonnet", "nomic-embed-text"],
        "estimated_storage_gb": 4.0,
        "required_ram_gb": 8.0,
    }
]


class ModelRegistryService:
    @staticmethod
    async def seed_default_models(db: AsyncSession) -> None:
        """Seed and synchronize default models and curated packages into PostgreSQL."""
        # Synchronize Models
        result = await db.execute(select(ModelRegistry))
        existing_models = {m.name: m for m in result.scalars().all()}
        
        for m_data in DEFAULT_MODELS:
            name = m_data["name"]
            if name not in existing_models:
                model = ModelRegistry(**m_data)
                db.add(model)
        
        # Synchronize Curated Packages
        pkg_result = await db.execute(select(ModelPackage))
        existing_pkgs = {p.slug: p for p in pkg_result.scalars().all()}
        
        for p_data in DEFAULT_PACKAGES:
            slug = p_data["slug"]
            if slug not in existing_pkgs:
                pkg = ModelPackage(**p_data)
                db.add(pkg)
            else:
                # Update existing package attributes to latest curated definitions
                pkg = existing_pkgs[slug]
                pkg.name = p_data["name"]
                pkg.description = p_data["description"]
                pkg.target_audience = p_data["target_audience"]
                pkg.recommended_model_ids = p_data["recommended_model_ids"]
                pkg.estimated_storage_gb = p_data["estimated_storage_gb"]
                pkg.required_ram_gb = p_data["required_ram_gb"]
        
        try:
            await db.commit()
            logger.info("Default AI models and curated model packages synchronized in PostgreSQL.")
        except Exception as e:
            await db.rollback()
            logger.warn(f"Notice syncing model registry defaults: {e}")

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
        
        # Query user settings for saved cloud API keys
        from backend.app.models.settings import UserSettings
        settings_res = await db.execute(select(UserSettings))
        user_settings = settings_res.scalars().first()
        custom_cfg = user_settings.custom_settings if user_settings else {}

        has_anthropic_key = bool(os.getenv("ANTHROPIC_API_KEY") or custom_cfg.get("anthropic_api_key"))
        has_openai_key = bool(os.getenv("OPENAI_API_KEY") or custom_cfg.get("openai_api_key"))
        has_groq_key = bool(os.getenv("GROQ_API_KEY") or custom_cfg.get("groq_api_key"))

        responses: List[ModelResponse] = []
        for m in models:
            # For local models, synchronize with verified local Ollama downloads
            if m.is_local:
                if installed_tags:
                    tag_matches = any(t == m.name or t.startswith(m.name.split(':')[0]) for t in installed_tags)
                    m.is_installed = tag_matches
                else:
                    m.is_installed = False
            else:
                # For cloud models, only marked installed/ready if user has entered their API key in Model Registry
                if "anthropic" in m.provider.lower() or "claude" in m.name.lower():
                    m.is_installed = has_anthropic_key
                elif "openai" in m.provider.lower() or "gpt" in m.name.lower():
                    m.is_installed = has_openai_key
                elif "groq" in m.provider.lower():
                    m.is_installed = has_groq_key
                else:
                    m.is_installed = has_anthropic_key or has_openai_key or has_groq_key

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
