from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CpuInfo(BaseModel):
    model: str = "Unknown"
    physical_cores: int = 1
    logical_cores: int = 1
    frequency_mhz: Optional[float] = None
    architecture: str = "x86_64"


class GpuInfo(BaseModel):
    name: str = "Integrated Graphics"
    vendor: str = "Unknown"
    vram_total_gb: float = 0.0
    vram_free_gb: Optional[float] = None
    cuda_supported: bool = False
    driver_version: Optional[str] = None


class RamInfo(BaseModel):
    total_gb: float = 0.0
    available_gb: float = 0.0
    used_gb: float = 0.0
    percent_used: float = 0.0


class StorageInfo(BaseModel):
    total_gb: float = 0.0
    free_gb: float = 0.0
    used_gb: float = 0.0
    percent_used: float = 0.0


class HardwareProfile(BaseModel):
    os: str = "Windows"
    os_release: Optional[str] = None
    architecture: str = "x64"
    cpu: CpuInfo = Field(default_factory=CpuInfo)
    ram: RamInfo = Field(default_factory=RamInfo)
    ram_gb: float = 0.0
    gpu: List[GpuInfo] = Field(default_factory=list)
    vram_gb: float = 0.0
    storage: StorageInfo = Field(default_factory=StorageInfo)
    storage_free_gb: float = 0.0
    accelerators: List[str] = Field(default_factory=list)
    compute_tier: str = "Standard" # Ultra, High, Medium, Low, Minimum
    detected_at: datetime = Field(default_factory=utc_now)
    recommendations_summary: str = ""

    model_config = ConfigDict(from_attributes=True)


class SystemProfileResponse(BaseModel):
    id: Optional[str] = None
    profile: HardwareProfile
    status: str = "success"

    model_config = ConfigDict(from_attributes=True)
