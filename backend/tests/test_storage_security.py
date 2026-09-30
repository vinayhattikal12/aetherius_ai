import os
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.storage_service import StorageService, StorageSecurityError, MAX_UPLOAD_SIZE_BYTES


def test_storage_safe_save_and_read(tmp_path):
    storage = StorageService(base_dir=str(tmp_path))
    content = b"Hello world secure storage test"
    
    saved_path = storage.save_file(content, "test.txt", subfolder="test_folder")
    assert os.path.exists(saved_path)
    assert os.path.commonpath([saved_path, str(tmp_path)]) == str(tmp_path)
    
    read_bytes = storage.read_file(saved_path)
    assert read_bytes == content


def test_storage_path_traversal_blocked(tmp_path):
    storage = StorageService(base_dir=str(tmp_path))
    
    # Attempting traversal in filename
    content = b"malicious content"
    saved_path = storage.save_file(content, "../../../evil.txt", subfolder="uploads")
    # File should be saved safely inside tmp_path / uploads, not escaping
    assert os.path.commonpath([saved_path, str(tmp_path)]) == str(tmp_path)
    assert "evil" in os.path.basename(saved_path)
    
    # Attempting traversal via subfolder
    with pytest.raises(StorageSecurityError):
        storage.resolve_safe_path("foo.txt", subfolder="../../../etc")


def test_storage_read_delete_outside_base_forbidden(tmp_path):
    storage = StorageService(base_dir=str(tmp_path))
    
    with pytest.raises((StorageSecurityError, FileNotFoundError)):
        storage.read_file("../../../etc/passwd")

    with pytest.raises((StorageSecurityError, FileNotFoundError)):
        storage.delete_file("../../../etc/passwd")


def test_storage_max_upload_size_enforced(tmp_path):
    storage = StorageService(base_dir=str(tmp_path))
    oversized = b"0" * (MAX_UPLOAD_SIZE_BYTES + 10)
    
    with pytest.raises(ValueError, match="exceeds maximum allowed size"):
        storage.save_file(oversized, "big.dat")


def test_chat_images_path_traversal_endpoint(tmp_path):
    client = TestClient(app)
    
    # Test directory traversal attacks
    resp1 = client.get("/api/v1/chat/images/..%2f..%2fetc%2fpasswd")
    assert resp1.status_code in [400, 404]

    resp2 = client.get("/api/v1/chat/images/....//secret.png")
    assert resp2.status_code in [400, 404]

    resp3 = client.get("/api/v1/chat/images/invalid_extension.exe")
    assert resp3.status_code == 400

    resp4 = client.get("/api/v1/chat/images/non_existent.png")
    assert resp4.status_code == 404
