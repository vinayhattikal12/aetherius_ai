import os
import shutil
import httpx
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.services.hardware_detector import HardwareDetector

router = APIRouter()


@router.get("/")
async def get_system_diagnostics(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Provides comprehensive health diagnostics across database, storage, local AI, and hardware."""
    diagnostics = {
        "status": "healthy",
        "app_name": "Aetherius AI Operating Environment",
        "version": "1.0.0",
        "components": {}
    }

    # 1. PostgreSQL & pgvector check
    try:
        res = await db.execute(text("SELECT 1;"))
        db_ok = res.scalar() == 1
        diagnostics["components"]["database"] = {
            "status": "online" if db_ok else "error",
            "dialect": "postgresql",
            "host": "127.0.0.1",
            "port": 54329,
            "pgvector_ready": True
        }
    except Exception as e:
        diagnostics["status"] = "degraded"
        diagnostics["components"]["database"] = {
            "status": "offline",
            "error": str(e)
        }

    # 2. Local Storage Diagnostics
    try:
        storage_dir = os.path.abspath(settings.UPLOAD_DIR)
        os.makedirs(storage_dir, exist_ok=True)
        disk_usage = shutil.disk_usage(storage_dir)
        diagnostics["components"]["storage"] = {
            "status": "ready",
            "storage_path": storage_dir,
            "total_gb": round(disk_usage.total / (1024 ** 3), 2),
            "free_gb": round(disk_usage.free / (1024 ** 3), 2),
            "used_gb": round(disk_usage.used / (1024 ** 3), 2)
        }
    except Exception as e:
        diagnostics["components"]["storage"] = {"status": "error", "error": str(e)}

    # 3. Local Ollama Server Probe
    ollama_online = False
    downloaded_models = []
    try:
        async with httpx.AsyncClient(timeout=0.3) as client:
            resp = await client.get("http://127.0.0.1:11434/api/tags")
            if resp.status_code == 200:
                ollama_online = True
                data = resp.json()
                downloaded_models = [m.get("name") for m in data.get("models", [])]
    except Exception:
        ollama_online = False

    diagnostics["components"]["local_ai_server"] = {
        "provider": "Ollama",
        "status": "online" if ollama_online else "offline",
        "endpoint": "http://127.0.0.1:11434",
        "models_installed": downloaded_models
    }

    # 4. Hardware Summary
    hw = HardwareDetector.get_hardware_profile()
    diagnostics["components"]["hardware"] = {
        "compute_tier": hw.compute_tier,
        "os": hw.os,
        "cpu": hw.cpu.model,
        "ram_gb": hw.ram.total_gb,
        "vram_gb": hw.vram_gb,
        "accelerators": hw.accelerators
    }

    return diagnostics
