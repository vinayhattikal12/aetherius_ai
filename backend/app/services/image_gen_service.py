import os
import re
import uuid
import base64
import random
import urllib.parse
import httpx
from typing import Optional, Dict, Any
from pydantic import BaseModel
from backend.app.core.logging import logger
from backend.app.services.storage_service import storage


class ImageGenerationRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    aspect_ratio: str = "1:1"  # "1:1", "16:9", "9:16", "4:3", "3:2"
    style_preset: Optional[str] = None  # "diagram", "photorealistic", "schematic", "3d", "anime"
    workspace_slug: str = "general"
    model_preference: Optional[str] = "fast-turbo"


class ImageGenerationResponse(BaseModel):
    image_url: str
    preview_url: Optional[str] = None
    prompt: str
    revised_prompt: Optional[str] = None
    aspect_ratio: str
    provider: str
    model_name: str
    width: int
    height: int
    seed: int


from backend.app.core.config import settings


class ImageGenService:
    """Multi-modal image generation service with local persistence and honest error handling."""

    ASPECT_RATIO_DIMENSIONS = {
        "1:1": (1024, 1024),
        "16:9": (1280, 720),
        "9:16": (720, 1280),
        "4:3": (1024, 768),
        "3:2": (1080, 720),
    }

    @classmethod
    def _enhance_prompt(cls, prompt: str, style: Optional[str]) -> str:
        prompt_clean = prompt.strip()
        
        # 1. Clean common conversational wrappers iteratively
        for _ in range(3):
            for pattern in [
                r"^(show|give|draw|generate|create|make|render)\s+(me\s+)?(an?\s+|the\s+)?(image|picture|diagram|photo|illustration|visual)\s+(of\s+|for\s+|showing\s+|about\s+)?",
                r"^with\s+(the\s+)?(help\s+of\s+)?(an?\s+)?(image|picture|diagram|illustration|visual)\s+(of\s+)?",
                r"^(generate|create|draw|paint|make|show|render)\s+(an?|the|its|this|a)?\s*(image|picture|diagram|photo|illustration|visual)?\s*(of|for|about)?\s*",
                r"^(draw|paint|sketch|visualize|illustrate|render)\s+(a|an|the|me)?\s*",
                r"^(explain|expalin|describe|show)\s+(to\s+me\s+)?",
                r"\s+(with|using)\s+(the\s+)?(help\s+of\s+)?(an?\s+)?(image|picture|diagram|illustration|visual)$"
            ]:
                prompt_clean = re.sub(pattern, "", prompt_clean, flags=re.IGNORECASE).strip()

        # 2. Fix common prompt typos
        typo_map = {
            "strret": "street",
            "stret": "street",
            "diagarm": "diagram",
            "diaram": "diagram",
            "peopel": "people",
            "computr": "computer",
            "sofware": "software",
            "artifical": "artificial",
            "architechture": "architecture",
            "expalin": "explain",
        }
        words = prompt_clean.split()
        cleaned_words = [typo_map.get(w.lower(), w) for w in words]
        prompt_clean = " ".join(cleaned_words)

        # 3. Domain concept expansions
        lower_clean = prompt_clean.lower().strip()
        if lower_clean in ["ai", "artificial intelligence", "its", "it", "this"] or not lower_clean:
            prompt_clean = "artificial intelligence neural networks deep learning and generative AI architecture diagram"
            style = "diagram"

        if not style:
            style = "diagram" if ("diagram" in lower_clean or "architecture" in lower_clean or "network" in lower_clean or "system" in lower_clean) else "photorealistic"

        style_modifiers = {
            "diagram": "clear architectural schematic diagram, high-resolution visual explanation, clean lines, labeled components, technical infographic, professional presentation style",
            "schematic": "detailed engineering schematic, blueprint styling, clean lines, technical drafting, precise typography and annotations",
            "photorealistic": "hyper-realistic 8k photograph, high dynamic range, intricate details, natural lighting, cinematic composition",
            "3d": "3D render, Octane render, smooth lighting, volumetric illumination, high fidelity, 4k texture",
            "concept_art": "digital concept art, vivid lighting, atmospheric matte painting, masterpiece illustration",
        }
        mod = style_modifiers.get(style.lower(), "")
        if mod and mod not in prompt_clean:
            return f"{prompt_clean}, {mod}"
        return prompt_clean

    @classmethod
    async def generate_image(cls, req: ImageGenerationRequest) -> ImageGenerationResponse:
        """
        Generate image using configured diffusion provider.
        Enforces LOCAL_ONLY boundaries and avoids fake generated placeholders.
        """
        if settings.LOCAL_ONLY:
            raise RuntimeError("Image generation is disabled in LOCAL_ONLY mode because no local diffusion engine is configured.")

        width, height = cls.ASPECT_RATIO_DIMENSIONS.get(req.aspect_ratio, (1024, 1024))
        enhanced_prompt = cls._enhance_prompt(req.prompt, req.style_preset)
        encoded_prompt = urllib.parse.quote(enhanced_prompt)

        seed = random.randint(100000, 999999)
        remote_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={seed}&nologo=true&enhance=true"

        image_bytes: Optional[bytes] = None
        ext = "jpg"
        mime_type = "image/jpeg"

        # 1. Download image bytes from diffusion provider
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                res = await client.get(remote_url)
                if res.status_code == 200 and len(res.content) > 1000:
                    image_bytes = res.content
                    content_type = res.headers.get("content-type", "")
                    if "png" in content_type:
                        ext = "png"
                        mime_type = "image/png"
                    elif "webp" in content_type:
                        ext = "webp"
                        mime_type = "image/webp"
                else:
                    raise RuntimeError(f"Diffusion provider returned HTTP status {res.status_code}")
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            raise RuntimeError(f"Image generation failed: {e}")

        # 2. Save file locally in storage
        filename = f"gen_{uuid.uuid4().hex[:12]}.{ext}"
        saved_path = storage.save_file(image_bytes, filename, subfolder="generated_images")
        saved_filename = os.path.basename(saved_path)

        # 3. Generate base64 Data URI for instant local preview
        b64_str = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:{mime_type};base64,{b64_str}"

        # 4. Build local API serving URL
        local_url = f"http://127.0.0.1:8000/api/v1/chat/images/{saved_filename}"

        return ImageGenerationResponse(
            image_url=local_url,
            preview_url=data_uri,
            prompt=req.prompt,
            revised_prompt=enhanced_prompt,
            aspect_ratio=req.aspect_ratio,
            provider="pollinations-flux-turbo",
            model_name="FLUX.1-Turbo / SD-Turbo",
            width=width,
            height=height,
            seed=seed,
        )

