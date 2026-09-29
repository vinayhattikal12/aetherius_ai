import os
import shutil
import hashlib
from typing import Optional
from backend.app.core.logging import logger


class StorageService:
    """Storage abstraction for Aetherius documents, model files, and cache."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.join(os.getcwd(), "data", "storage")
        os.makedirs(os.path.join(self.base_dir, "uploads"), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, "cache"), exist_ok=True)

    def save_file(self, content_bytes: bytes, filename: str, subfolder: str = "uploads") -> str:
        folder = os.path.join(self.base_dir, subfolder)
        os.makedirs(folder, exist_ok=True)
        
        # Calculate file sha256 to avoid collisions
        file_hash = hashlib.sha256(content_bytes).hexdigest()[:12]
        base_name, ext = os.path.splitext(filename)
        safe_filename = f"{base_name}_{file_hash}{ext}"
        full_path = os.path.join(folder, safe_filename)

        with open(full_path, "wb") as f:
            f.write(content_bytes)

        logger.info(f"Stored file: {full_path} ({len(content_bytes)} bytes)")
        return full_path

    def read_file(self, file_path: str) -> bytes:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(file_path, "rb") as f:
            return f.read()

    def delete_file(self, file_path: str) -> bool:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False


storage = StorageService()
