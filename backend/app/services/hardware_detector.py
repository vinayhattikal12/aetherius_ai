import os
import platform
import subprocess
import psutil
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.app.schemas.system import (
    HardwareProfile,
    CpuInfo,
    GpuInfo,
    RamInfo,
    StorageInfo
)
from backend.app.core.logging import logger


class HardwareDetector:
    """Production-grade hardware and system capability detector for Aetherius."""

    @staticmethod
    def detect_cpu() -> CpuInfo:
        cpu_model = platform.processor() or "Unknown CPU"
        physical_cores = psutil.cpu_count(logical=False) or 1
        logical_cores = psutil.cpu_count(logical=True) or 1
        freq = psutil.cpu_freq()
        freq_mhz = freq.current if freq else None

        # Enhance CPU model name on Windows / Linux
        if platform.system() == "Windows":
            try:
                out = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name"],
                    stderr=subprocess.DEVNULL,
                    text=True
                ).strip()
                if out:
                    cpu_model = out
            except Exception:
                pass
        elif platform.system() == "Linux":
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if "model name" in line:
                            cpu_model = line.split(":")[1].strip()
                            break
            except Exception:
                pass

        return CpuInfo(
            model=cpu_model,
            physical_cores=physical_cores,
            logical_cores=logical_cores,
            frequency_mhz=freq_mhz,
            architecture=platform.machine()
        )

    @staticmethod
    def detect_ram() -> RamInfo:
        vmem = psutil.virtual_memory()
        to_gb = 1024 ** 3
        return RamInfo(
            total_gb=round(vmem.total / to_gb, 2),
            available_gb=round(vmem.available / to_gb, 2),
            used_gb=round(vmem.used / to_gb, 2),
            percent_used=vmem.percent
        )

    @staticmethod
    def detect_storage() -> StorageInfo:
        try:
            # Check current workspace root or system root disk
            path = os.getcwd()
            disk = psutil.disk_usage(path)
            to_gb = 1024 ** 3
            return StorageInfo(
                total_gb=round(disk.total / to_gb, 2),
                free_gb=round(disk.free / to_gb, 2),
                used_gb=round(disk.used / to_gb, 2),
                percent_used=disk.percent
            )
        except Exception as e:
            logger.warning(f"Disk detection notice: {e}")
            return StorageInfo(total_gb=100.0, free_gb=50.0, used_gb=50.0, percent_used=50.0)

    @staticmethod
    def detect_gpus() -> List[GpuInfo]:
        gpus: List[GpuInfo] = []
        sys_name = platform.system()

        # 1. Try NVIDIA-SMI first for accurate VRAM and CUDA
        try:
            res = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
            if res:
                for line in res.splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        name = parts[0]
                        total_mb = float(parts[1]) if parts[1].replace('.', '', 1).isdigit() else 0.0
                        free_mb = float(parts[2]) if parts[2].replace('.', '', 1).isdigit() else 0.0
                        driver = parts[3] if len(parts) > 3 else None
                        gpus.append(GpuInfo(
                            name=name,
                            vendor="NVIDIA",
                            vram_total_gb=round(total_mb / 1024.0, 2),
                            vram_free_gb=round(free_mb / 1024.0, 2),
                            cuda_supported=True,
                            driver_version=driver
                        ))
                if gpus:
                    return gpus
        except Exception:
            pass

        # 2. Windows CIM / WMI fallback
        if sys_name == "Windows":
            try:
                ps_cmd = 'Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion | ConvertTo-Json'
                out = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    stderr=subprocess.DEVNULL,
                    text=True
                ).strip()
                if out:
                    import json
                    data = json.loads(out)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        name = item.get("Name", "Graphics Adapter")
                        raw_ram = item.get("AdapterRAM", 0) or 0
                        vram_gb = round(raw_ram / (1024 ** 3), 2) if raw_ram > 0 else 0.0
                        driver = item.get("DriverVersion")
                        vendor = "NVIDIA" if "NVIDIA" in name.upper() else ("AMD" if "AMD" in name.upper() or "RADEON" in name.upper() else ("Intel" if "INTEL" in name.upper() else "Generic"))
                        cuda = vendor == "NVIDIA"
                        gpus.append(GpuInfo(
                            name=name,
                            vendor=vendor,
                            vram_total_gb=vram_gb,
                            vram_free_gb=vram_gb,
                            cuda_supported=cuda,
                            driver_version=driver
                        ))
            except Exception as e:
                logger.warning(f"Windows GPU detection notice: {e}")

        # Fallback if no GPU detected
        if not gpus:
            gpus.append(GpuInfo(
                name="Standard Integrated / CPU Graphics",
                vendor="System",
                vram_total_gb=0.0,
                cuda_supported=False
            ))

        return gpus

    @classmethod
    def detect_accelerators(cls, gpus: List[GpuInfo]) -> List[str]:
        accels = []
        for g in gpus:
            if g.cuda_supported:
                accels.append("CUDA (NVIDIA)")
            elif "AMD" in g.vendor.upper() or "RADEON" in g.name.upper():
                accels.append("ROCm / DirectML (AMD)")
            elif "INTEL" in g.vendor.upper():
                accels.append("OpenVINO / DirectML (Intel)")

        if platform.system() == "Darwin":
            accels.append("Metal (Apple Silicon)")

        if platform.system() == "Windows":
            accels.append("DirectML")

        accels.append("CPU (AVX2/FMA)")
        return list(dict.fromkeys(accels))

    @classmethod
    def calculate_compute_tier(cls, ram_gb: float, vram_gb: float, has_cuda: bool) -> str:
        if vram_gb >= 16.0 or (ram_gb >= 64.0 and has_cuda):
            return "Ultra"
        elif vram_gb >= 8.0 or (ram_gb >= 32.0 and has_cuda):
            return "High"
        elif vram_gb >= 4.0 or ram_gb >= 16.0:
            return "Medium"
        elif ram_gb >= 8.0:
            return "Low"
        return "Minimum"

    @classmethod
    def get_hardware_profile(cls) -> HardwareProfile:
        cpu = cls.detect_cpu()
        ram = cls.detect_ram()
        storage = cls.detect_storage()
        gpus = cls.detect_gpus()
        
        total_vram = sum(g.vram_total_gb for g in gpus)
        has_cuda = any(g.cuda_supported for g in gpus)
        accelerators = cls.detect_accelerators(gpus)
        tier = cls.calculate_compute_tier(ram.total_gb, total_vram, has_cuda)

        # Human-friendly summary
        summary = f"Detected {cpu.physical_cores}-core {cpu.model}, {ram.total_gb} GB RAM"
        if total_vram > 0:
            summary += f", {gpus[0].name} ({total_vram} GB VRAM)"
        summary += f" — Tier: {tier}"

        return HardwareProfile(
            os=platform.system(),
            os_release=platform.release(),
            architecture=platform.machine(),
            cpu=cpu,
            ram=ram,
            ram_gb=ram.total_gb,
            gpu=gpus,
            vram_gb=total_vram,
            storage=storage,
            storage_free_gb=storage.free_gb,
            accelerators=accelerators,
            compute_tier=tier,
            detected_at=datetime.now(timezone.utc),
            recommendations_summary=summary
        )
