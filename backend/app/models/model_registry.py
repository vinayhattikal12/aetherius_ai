from sqlalchemy import String, Integer, Float, Boolean, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.models.base import BaseModel


class ModelRegistry(BaseModel):
    __tablename__ = "models"

    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False) # ollama, llamacpp, openai, anthropic, google, openrouter
    model_family: Mapped[str] = mapped_column(String(50), nullable=False) # llama, qwen, mistral, gemma, deepseek, claude, gpt
    
    parameters_b: Mapped[float] = mapped_column(Float, default=0.0) # e.g. 1.5, 3.0, 7.0, 8.0, 14.0, 70.0
    quantization: Mapped[str] = mapped_column(String(20), default="Q4_K_M") # Q4_K_M, Q8_0, FP16, None
    context_size: Mapped[int] = mapped_column(Integer, default=4096)
    
    min_ram_gb: Mapped[float] = mapped_column(Float, default=4.0)
    min_vram_gb: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_vram_gb: Mapped[float] = mapped_column(Float, default=4.0)
    
    cpu_compatible: Mapped[bool] = mapped_column(Boolean, default=True)
    gpu_compatible: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Capability flags
    vision_capable: Mapped[bool] = mapped_column(Boolean, default=False)
    coding_capable: Mapped[bool] = mapped_column(Boolean, default=False)
    reasoning_capable: Mapped[bool] = mapped_column(Boolean, default=False)
    tool_calling_capable: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding_capable: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Role category tag
    category: Mapped[str] = mapped_column(String(50), default="General") # General, Coding, Fast, Reasoning, Multimodal, Embedding
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Installation & availability state
    is_local: Mapped[bool] = mapped_column(Boolean, default=True)
    is_installed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class ModelPackage(BaseModel):
    __tablename__ = "model_packages"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target_audience: Mapped[str] = mapped_column(String(100), nullable=False)
    recommended_model_ids: Mapped[list] = mapped_column(JSON, default=list) # list of model identifiers
    estimated_storage_gb: Mapped[float] = mapped_column(Float, default=0.0)
    required_ram_gb: Mapped[float] = mapped_column(Float, default=8.0)
