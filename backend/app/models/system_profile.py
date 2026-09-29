from sqlalchemy import String, Integer, Float, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.models.base import BaseModel


class SystemProfile(BaseModel):
    __tablename__ = "system_profiles"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    os_name: Mapped[str] = mapped_column(String(50), nullable=False) # Windows, Linux, Darwin
    os_release: Mapped[str] = mapped_column(String(100), nullable=True)
    architecture: Mapped[str] = mapped_column(String(50), nullable=False) # x86_64, arm64
    
    cpu_model: Mapped[str] = mapped_column(String(255), nullable=True)
    cpu_physical_cores: Mapped[int] = mapped_column(Integer, default=1)
    cpu_logical_cores: Mapped[int] = mapped_column(Integer, default=1)
    
    ram_total_gb: Mapped[float] = mapped_column(Float, default=0.0)
    ram_available_gb: Mapped[float] = mapped_column(Float, default=0.0)
    
    gpu_models: Mapped[list] = mapped_column(JSON, default=list)
    vram_total_gb: Mapped[float] = mapped_column(Float, default=0.0)
    
    storage_total_gb: Mapped[float] = mapped_column(Float, default=0.0)
    storage_free_gb: Mapped[float] = mapped_column(Float, default=0.0)
    
    accelerators: Mapped[list] = mapped_column(JSON, default=list) # CUDA, ROCm, Metal, DirectML, CPU
    compute_tier: Mapped[str] = mapped_column(String(50), default="Standard") # Ultra, High, Medium, Low, Minimum
    
    raw_telemetry: Mapped[dict] = mapped_column(JSON, default=dict)

    # Relationships
    user = relationship("User", back_populates="system_profiles")
