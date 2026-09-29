import pytest
from backend.app.services.hardware_detector import HardwareDetector
from backend.app.schemas.system import HardwareProfile, GpuInfo


def test_hardware_detector_runs_and_returns_valid_profile():
    profile = HardwareDetector.get_hardware_profile()
    assert isinstance(profile, HardwareProfile)
    assert profile.os in ["Windows", "Linux", "Darwin"]
    assert profile.cpu.physical_cores >= 1
    assert profile.ram.total_gb > 0
    assert profile.storage.total_gb > 0
    assert profile.compute_tier in ["Ultra", "High", "Medium", "Low", "Minimum"]
    assert len(profile.accelerators) >= 1


def test_compute_tier_calculation():
    # Ultra: 24GB VRAM
    assert HardwareDetector.calculate_compute_tier(64.0, 24.0, True) == "Ultra"
    # High: 8GB VRAM
    assert HardwareDetector.calculate_compute_tier(32.0, 8.0, True) == "High"
    # Medium: 16GB RAM, no dedicated GPU
    assert HardwareDetector.calculate_compute_tier(16.0, 0.0, False) == "Medium"
    # Low: 8GB RAM
    assert HardwareDetector.calculate_compute_tier(8.0, 0.0, False) == "Low"
    # Minimum: 4GB RAM
    assert HardwareDetector.calculate_compute_tier(4.0, 0.0, False) == "Minimum"
