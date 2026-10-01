import os
from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import FileResponse, Response
from backend.app.services.artifact_service import ArtifactService

router = APIRouter()


@router.get("/{artifact_id}/metadata")
async def get_artifact_metadata(artifact_id: str = Path(..., description="UUID of the generated artifact")):
    """Get metadata for a generated document artifact."""
    artifact = ArtifactService.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found or expired.")
    return artifact.model_dump()


@router.get("/{artifact_id}/download")
async def download_artifact(artifact_id: str = Path(..., description="UUID of the generated artifact")):
    """Download the generated artifact file directly."""
    artifact = ArtifactService.get_artifact(artifact_id)
    if not artifact or not os.path.exists(artifact.file_path):
        raise HTTPException(status_code=404, detail="Artifact file not found.")

    return FileResponse(
        path=artifact.file_path,
        media_type=artifact.mime_type,
        filename=artifact.filename,
        headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'}
    )


@router.get("/{artifact_id}/preview")
async def preview_artifact(artifact_id: str = Path(..., description="UUID of the generated artifact")):
    """Inline stream for browser-based preview (e.g. built-in PDF viewer or image display)."""
    artifact = ArtifactService.get_artifact(artifact_id)
    if not artifact or not os.path.exists(artifact.file_path):
        raise HTTPException(status_code=404, detail="Artifact file not found.")

    return FileResponse(
        path=artifact.file_path,
        media_type=artifact.mime_type,
        headers={"Content-Disposition": f'inline; filename="{artifact.filename}"'}
    )
