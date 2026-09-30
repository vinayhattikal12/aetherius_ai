import os
import shutil
import hashlib
import re
from pathlib import Path
from typing import Optional
from backend.app.core.logging import logger

MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class StorageSecurityError(ValueError):
    """Raised when an unsafe path or security violation is detected."""
    pass


class StorageService:
    """Storage abstraction for Aetherius documents, model files, and cache."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = os.path.abspath(base_dir or os.path.join(os.getcwd(), "data", "storage"))
        os.makedirs(os.path.join(self.base_dir, "uploads"), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, "cache"), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, "chat_attachments"), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, "generated_images"), exist_ok=True)

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent directory traversal and invalid characters."""
        if not filename:
            return "unnamed_file"
        # Extract only base filename, stripping any directory components
        base = os.path.basename(filename.replace("\\", "/"))
        # Remove null bytes and control chars
        base = re.sub(r"[\x00-\x1f\x7f]", "", base)
        # Keep only alphanumeric, dots, underscores, dashes
        safe_name = re.sub(r"[^\w\.\-]", "_", base).strip("._")
        return safe_name if safe_name else "unnamed_file"

    def resolve_safe_path(self, relative_path: str, subfolder: Optional[str] = None) -> str:
        """Resolve path ensuring it strictly resides within base_dir."""
        target_dir = self.base_dir
        if subfolder:
            target_dir = os.path.abspath(os.path.join(self.base_dir, subfolder))
        
        full_path = os.path.abspath(os.path.join(target_dir, relative_path))
        
        # Verify that full_path is strictly within base_dir
        try:
            common = os.path.commonpath([full_path, self.base_dir])
        except ValueError:
            raise StorageSecurityError(f"Cross-drive or invalid path access: {full_path}")
            
        if common != self.base_dir:
            raise StorageSecurityError(f"Directory traversal detected: {full_path}")
            
        return full_path

    def save_file(self, content_bytes: bytes, filename: str, subfolder: str = "uploads") -> str:
        if len(content_bytes) > MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(f"File size exceeds maximum allowed size of {MAX_UPLOAD_SIZE_BYTES} bytes")

        safe_name = self.sanitize_filename(filename)
        base_name, ext = os.path.splitext(safe_name)
        file_hash = hashlib.sha256(content_bytes).hexdigest()[:12]
        unique_name = f"{base_name}_{file_hash}{ext}"

        full_path = self.resolve_safe_path(unique_name, subfolder=subfolder)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "wb") as f:
            f.write(content_bytes)

        logger.info(f"Stored file: {full_path} ({len(content_bytes)} bytes)")
        return full_path

    def read_file(self, file_path: str) -> bytes:
        safe_path = self.resolve_safe_path(file_path) if not os.path.isabs(file_path) else os.path.abspath(file_path)
        try:
            if os.path.commonpath([safe_path, self.base_dir]) != self.base_dir:
                raise StorageSecurityError(f"Access to file outside storage base is forbidden: {file_path}")
        except ValueError:
            raise StorageSecurityError(f"Invalid path: {file_path}")

        if not os.path.exists(safe_path) or not os.path.isfile(safe_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(safe_path, "rb") as f:
            return f.read()

    def delete_file(self, file_path: str) -> bool:
        safe_path = self.resolve_safe_path(file_path) if not os.path.isabs(file_path) else os.path.abspath(file_path)
        try:
            if os.path.commonpath([safe_path, self.base_dir]) != self.base_dir:
                raise StorageSecurityError(f"Access to file outside storage base is forbidden: {file_path}")
        except ValueError:
            raise StorageSecurityError(f"Invalid path: {file_path}")

        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            os.remove(safe_path)
            return True
        return False


storage = StorageService()

