from typing import Dict, Any, Tuple, List
from backend.app.schemas.system import HardwareProfile
from backend.app.schemas.model_registry import CompatibilityResult, ModelBase


class ModelCompatibilityEngine:
    """Evaluates compatibility between a given hardware profile and target LLM / embedding models."""

    @classmethod
    def estimate_model_memory_gb(cls, parameters_b: float, quantization: str, context_size: int = 4096) -> float:
        """
        Estimates total RAM / VRAM footprint in GB for a model.
        Formula: (Parameters * bits_per_weight / 8) + KV cache allowance.
        """
        if parameters_b <= 0:
            return 1.0 # Cloud / API model or tiny utility

        bits_map = {
            "Q2_K": 2.8,
            "Q3_K_M": 3.7,
            "Q4_0": 4.5,
            "Q4_K_M": 4.8,
            "Q5_K_M": 5.7,
            "Q6_K": 6.8,
            "Q8_0": 8.5,
            "FP16": 16.0,
            "BF16": 16.0,
            "FP32": 32.0,
        }
        bpw = bits_map.get(quantization.upper(), 4.8)
        weights_gb = (parameters_b * bpw) / 8.0
        
        # KV Cache estimate (~0.5 GB per 4k tokens for standard 7B-8B models)
        kv_cache_gb = (context_size / 4096.0) * (parameters_b / 7.0) * 0.6
        total_gb = weights_gb + kv_cache_gb + 0.3 # runtime overhead
        return round(total_gb, 2)

    @classmethod
    def evaluate(cls, profile: HardwareProfile, model: ModelBase | Dict[str, Any]) -> CompatibilityResult:
        if isinstance(model, dict):
            name = model.get("name", "Unknown")
            is_local = model.get("is_local", True)
            params_b = float(model.get("parameters_b", 0.0))
            quantization = model.get("quantization", "Q4_K_M")
            context_size = int(model.get("context_size", 4096))
            min_ram_gb = float(model.get("min_ram_gb", 4.0))
            min_vram_gb = float(model.get("min_vram_gb", 0.0))
        else:
            name = model.name
            is_local = model.is_local
            params_b = model.parameters_b
            quantization = model.quantization
            context_size = model.context_size
            min_ram_gb = model.min_ram_gb
            min_vram_gb = model.min_vram_gb

        # 1. Cloud-based models are universally compatible as long as network exists
        if not is_local or params_b == 0:
            return CompatibilityResult(
                model_name=name,
                compatibility="Compatible",
                score=100,
                estimated_memory_gb=0.1,
                recommended_quantization="API / Cloud Hosted",
                recommended_execution="Cloud",
                performance_tier="Fast / Fluid",
                reasons=["Cloud API model executes remotely; requires negligible local memory."]
            )

        # 2. Local model evaluation
        estimated_mem = cls.estimate_model_memory_gb(params_b, quantization, context_size)
        total_ram = profile.ram.total_gb if profile.ram else profile.ram_gb
        avail_ram = profile.ram.available_gb if profile.ram else total_ram * 0.7
        total_vram = profile.vram_gb
        has_cuda = any(g.cuda_supported for g in profile.gpu)

        reasons: List[str] = []
        score = 100
        recommended_quant = "Q4_K_M"

        # Check VRAM offloading
        fits_in_vram = total_vram >= estimated_mem
        fits_in_ram = avail_ram >= estimated_mem or total_ram >= (estimated_mem + 3.0)

        if fits_in_vram and total_vram > 0:
            recommended_exec = "Local (GPU)"
            perf_tier = "Fast / Fluid"
            status = "Compatible"
            score = 95
            reasons.append(f"Model ({estimated_mem:.1f} GB) fits entirely within your GPU VRAM ({total_vram:.1f} GB).")
            if total_vram >= estimated_mem * 1.5:
                recommended_quant = "Q8_0" if params_b <= 8.0 else "Q5_K_M"
        elif fits_in_ram:
            if total_vram > 2.0:
                recommended_exec = "Hybrid (GPU + CPU)"
                perf_tier = "Moderate / Usable"
                status = "Compatible"
                score = 80
                reasons.append(f"Model will split layers between GPU VRAM ({total_vram:.1f} GB) and System RAM ({total_ram:.1f} GB).")
            else:
                recommended_exec = "Local (CPU/RAM)"
                perf_tier = "Moderate / Usable" if profile.cpu.physical_cores >= 6 else "Slow / Heavy"
                status = "Compatible" if total_ram >= (estimated_mem + 4.0) else "Maybe Compatible"
                score = 70 if status == "Compatible" else 55
                reasons.append(f"Model will run on CPU with {total_ram:.1f} GB RAM ({profile.cpu.physical_cores} CPU cores).")
                recommended_quant = "Q4_K_M"
        else:
            # Memory constrained
            if total_ram >= min_ram_gb:
                recommended_exec = "Local (CPU/RAM - High Quantized)"
                perf_tier = "Slow / Heavy"
                status = "Maybe Compatible"
                score = 45
                recommended_quant = "Q3_K_M"
                reasons.append(f"System RAM ({total_ram:.1f} GB) is tight for {params_b}B parameters. Consider higher quantization or cloud.")
            else:
                recommended_exec = "Cloud / Remote"
                perf_tier = "Not Viable"
                status = "Not Recommended"
                score = 20
                reasons.append(f"Insufficient RAM ({total_ram:.1f} GB total) for local execution of this {params_b}B model.")

        # Storage check
        if profile.storage_free_gb > 0 and profile.storage_free_gb < (estimated_mem + 2.0):
            score = max(0, score - 25)
            reasons.append(f"Warning: Low disk space ({profile.storage_free_gb:.1f} GB free). Model requires ~{estimated_mem:.1f} GB download.")

        return CompatibilityResult(
            model_name=name,
            compatibility=status,
            score=score,
            estimated_memory_gb=estimated_mem,
            recommended_quantization=recommended_quant,
            recommended_execution=recommended_exec,
            performance_tier=perf_tier,
            reasons=reasons
        )
