import uuid
import base64
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatAttachment,
)
from backend.app.services.chat_service import ChatService
from backend.app.services.storage_service import storage
from backend.app.services.document_processor import DocumentProcessor
from backend.app.services.image_gen_service import (
    ImageGenService,
    ImageGenerationRequest,
    ImageGenerationResponse,
)

router = APIRouter()


@router.get("/images/{filename}")
async def get_generated_image(filename: str):
    """Serve locally stored generated images with optimal caching and content headers."""
    folder = os.path.join(storage.base_dir, "generated_images")
    file_path = os.path.join(folder, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Requested image not found")
        
    ext = os.path.splitext(filename)[1].lower()
    media_type = "image/png" if ext == ".png" else "image/svg+xml" if ext == ".svg" else "image/webp" if ext == ".webp" else "image/jpeg"
    
    return FileResponse(
        file_path,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=86400",
        }
    )



@router.post("/upload", response_model=ChatAttachment)
async def upload_chat_file(
    file: UploadFile = File(...)
):
    """Upload a document, spreadsheet, or image directly into the active chat session."""
    try:
        content_bytes = await file.read()
        filename = file.filename or "attachment"
        ext = os.path.splitext(filename)[1].lower().replace(".", "")
        
        # Save file to storage
        saved_path = storage.save_file(content_bytes, filename, subfolder="chat_attachments")
        
        # Check if file is image
        image_extensions = ["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"]
        is_img = ext in image_extensions or (file.content_type and "image" in file.content_type)
        
        preview_url = None
        extracted_text = None
        
        if is_img:
            # Generate inline base64 preview
            mime_type = file.content_type or f"image/{ext if ext != 'jpg' else 'jpeg'}"
            b64_content = base64.b64encode(content_bytes).decode("utf-8")
            preview_url = f"data:{mime_type};base64,{b64_content}"
        else:
            # Extract document text and summary
            try:
                extracted, _ = DocumentProcessor.extract_text(content_bytes, ext or "txt")
                extracted_text = extracted
            except Exception as ex:
                extracted_text = f"[Unable to parse {ext} text content: {ex}]"

        return ChatAttachment(
            id=str(uuid.uuid4()),
            filename=filename,
            file_type=file.content_type or ext or "application/octet-stream",
            file_size_bytes=len(content_bytes),
            storage_path=saved_path,
            is_image=is_img,
            preview_url=preview_url,
            extracted_text=extracted_text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process chat attachment: {str(e)}")


@router.post("/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(
    request: ChatCompletionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Execute complete chat completion with RAG synthesis, web search, and PostgreSQL persistence."""
    try:
        return await ChatService.process_chat_completion(db, request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream_chat_completion_endpoint(
    request: ChatCompletionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Stream chat completion tokens in real-time with Server-Sent Events (SSE)."""
    try:
        return StreamingResponse(
            ChatService.stream_chat_completion(db, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-image", response_model=ImageGenerationResponse)
async def generate_image_endpoint(
    request: ImageGenerationRequest
):
    """Generate high-resolution visual diagrams, schematics, or photorealistic images in real-time."""
    try:
        return await ImageGenService.generate_image(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")
