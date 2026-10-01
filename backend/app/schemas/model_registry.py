from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class ModelCapabilities(BaseModel):
    chat: bool = True
    reasoning: bool = True
    coding: bool = False
    vision: bool = False
    tool_calling: bool = False
    structured_output: bool = True
    long_context: bool = False


class ModelQualityProfile(BaseModel):
    reasoning: str = "medium"
    coding: str = "medium"
    instruction_following: str = "high"
    factuality: str = "high"


class ModelHardwareRequirements(BaseModel):
    ram: str = "4GB"
    vram: str = "0GB"
    gpu: str = "Optional"
    storage: str = "4GB"


class ModelDescriptor(BaseModel):
    """Normalized model descriptor representation for all local and cloud models."""
    model_id: str
    provider: str
    provider_model_id: str
    runtime: str = "ollama"  # "ollama", "cloud", "openai", "anthropic", "google", "groq"
    type: str = "local"      # "local", "cloud"
    architecture: str = "transformer"
    parameters: str = "3B"
    quantization: str = "Q4_K_M"
    context_length: int = 4096
    capabilities: ModelCapabilities = Field(default_factory=ModelCapabilities)
    quality_profile: ModelQualityProfile = Field(default_factory=ModelQualityProfile)
    hardware_requirements: ModelHardwareRequirements = Field(default_factory=ModelHardwareRequirements)


class ModelBase(BaseModel):
    name: str
    display_name: str
    provider: str
    model_family: str
    parameters_b: float = 0.0
    quantization: str = "Q4_K_M"
    context_size: int = 4096
    min_ram_gb: float = 4.0
    min_vram_gb: float = 0.0
    recommended_vram_gb: float = 4.0
    cpu_compatible: bool = True
    gpu_compatible: bool = True
    vision_capable: bool = False
    coding_capable: bool = False
    reasoning_capable: bool = False
    tool_calling_capable: bool = False
    embedding_capable: bool = False
    category: str = "General"
    description: Optional[str] = None
    is_local: bool = True
    descriptor: Optional[ModelDescriptor] = None
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelCreate(ModelBase):
    pass


class CompatibilityResult(BaseModel):
    model_name: str
    compatibility: str # "SUPPORTED", "POSSIBLE", "NOT_RECOMMENDED", "INCOMPATIBLE", "UNKNOWN"
    score: int # 0 to 100
    estimated_memory_gb: float
    recommended_quantization: str
    recommended_execution: str # "Local (GPU)", "Local (CPU/RAM)", "Cloud", "Hybrid", "UNKNOWN"
    performance_tier: str # "Fast / Fluid", "Moderate / Usable", "Slow / Heavy", "Not Viable", "UNKNOWN"
    reasons: List[str] = Field(default_factory=list)


class ModelResponse(ModelBase):
    id: str
    is_installed: bool = False
    is_recommended: bool = False
    is_active: bool = True
    compatibility: Optional[CompatibilityResult] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelPackageResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    target_audience: str
    recommended_model_ids: List[str] = Field(default_factory=list)
    models: List[ModelResponse] = Field(default_factory=list)
    estimated_storage_gb: float = 0.0
    required_ram_gb: float = 8.0

    model_config = ConfigDict(from_attributes=True)


class HuggingFaceModelCard(BaseModel):
    repo_id: str
    author: str
    model_name: str
    parameters_b: float
    quantization_formats: List[str] = Field(default_factory=list)
    downloads: int = 0
    likes: int = 0
    category: str = "General"
    description: str = ""
    is_gguf: bool = True
    ollama_pull_tag: str
    recommended_quantization: str = "Q4_K_M"
    estimated_size_gb: float = 4.5
    benchmark_highlight: Optional[str] = None
    compatibility: Optional[CompatibilityResult] = None


class HuggingFaceDatasetCard(BaseModel):
    repo_id: str
    author: str
    dataset_name: str
    description: str = ""
    downloads: int = 0
    likes: int = 0
    category: str = "General"
    tags: List[str] = Field(default_factory=list)


class ModelUpgradeSuggestion(BaseModel):
    current_model_id: str
    current_model_name: str
    suggested_repo_id: str
    suggested_display_name: str
    category: str
    reason: str
    benchmark_gain: str
    estimated_disk_delta_gb: float
    vram_fit_status: str
    compatibility: CompatibilityResult


class SmartSwapRequest(BaseModel):
    old_model_id: str
    new_repo_id: str
    quantization: str = "Q4_K_M"


class ModelInstallProgress(BaseModel):
    model_id: str
    model_name: str
    status: str  # "initializing", "downloading", "verifying", "registering", "completed", "failed"
    status_message: str
    progress_percent: float = 0.0  # 0.0 to 100.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed_mbps: Optional[float] = None
    eta_seconds: Optional[int] = None
    error: Optional[str] = None
    is_completed: bool = False

