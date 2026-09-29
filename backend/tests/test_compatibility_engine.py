import pytest
from backend.app.services.compatibility_engine import ModelCompatibilityEngine
from backend.app.services.hardware_detector import HardwareDetector
from backend.app.schemas.system import HardwareProfile, CpuInfo, RamInfo, StorageInfo, GpuInfo
from backend.app.schemas.model_registry import ModelBase


def test_estimate_model_memory():
    # 7B parameter Q4_K_M model should need ~4.5 - 5.5 GB
    mem_7b = ModelCompatibilityEngine.estimate_model_memory_gb(7.0, "Q4_K_M", 4096)
    assert 4.0 <= mem_7b <= 6.0

    # 70B parameter model
    mem_70b = ModelCompatibilityEngine.estimate_model_memory_gb(70.0, "Q4_K_M", 4096)
    assert mem_70b > 40.0


def test_compatibility_high_end_gpu():
    profile = HardwareProfile(
        os="Windows",
        architecture="x64",
        cpu=CpuInfo(model="AMD Ryzen 9", physical_cores=16, logical_cores=32),
        ram=RamInfo(total_gb=64.0, available_gb=50.0, used_gb=14.0, percent_used=22.0),
        ram_gb=64.0,
        gpu=[GpuInfo(name="NVIDIA RTX 4090", vendor="NVIDIA", vram_total_gb=24.0, cuda_supported=True)],
        vram_gb=24.0,
        storage=StorageInfo(total_gb=1000.0, free_gb=600.0, used_gb=400.0, percent_used=40.0),
        storage_free_gb=600.0,
        accelerators=["CUDA (NVIDIA)"],
        compute_tier="Ultra"
    )

    model_7b = ModelBase(
        name="qwen2.5-coder:7b",
        display_name="Qwen 2.5 Coder 7B",
        provider="ollama",
        model_family="qwen",
        parameters_b=7.0,
        quantization="Q4_K_M",
        context_size=8192,
        is_local=True
    )

    result = ModelCompatibilityEngine.evaluate(profile, model_7b)
    assert result.compatibility == "Compatible"
    assert result.score >= 90
    assert result.recommended_execution == "Local (GPU)"
    assert result.performance_tier == "Fast / Fluid"


def test_compatibility_low_end_laptop():
    profile = HardwareProfile(
        os="Windows",
        architecture="x64",
        cpu=CpuInfo(model="Intel Core i3", physical_cores=2, logical_cores=4),
        ram=RamInfo(total_gb=4.0, available_gb=1.2, used_gb=2.8, percent_used=70.0),
        ram_gb=4.0,
        gpu=[],
        vram_gb=0.0,
        storage=StorageInfo(total_gb=256.0, free_gb=10.0, used_gb=246.0, percent_used=96.0),
        storage_free_gb=10.0,
        accelerators=["CPU (AVX2/FMA)"],
        compute_tier="Minimum"
    )

    # Big 70B model
    model_70b = ModelBase(
        name="llama3:70b",
        display_name="Llama 3 70B",
        provider="ollama",
        model_family="llama",
        parameters_b=70.0,
        min_ram_gb=48.0,
        quantization="Q4_K_M",
        context_size=8192,
        is_local=True
    )

    result = ModelCompatibilityEngine.evaluate(profile, model_70b)
    assert result.compatibility == "Not Recommended"
    assert result.recommended_execution == "Cloud / Remote"
    assert result.performance_tier == "Not Viable"
