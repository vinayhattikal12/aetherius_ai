import re
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.model_registry import ModelRegistry
from backend.app.models.settings import UserSettings
from backend.app.models.system_profile import SystemProfile
from backend.app.schemas.router import RouterEvaluationRequest, RouterEvaluationResponse
from backend.app.schemas.intelligence import ResolvedTask
from backend.app.core.logging import logger


class ModelRouter:
    """
    Sub-millisecond Intelligent Intent Analyzer and Model Router.
    Selects the optimal execution model based on resolved task requirements,
    conversational complexity, workspace role, and system compute capability.
    """

    @staticmethod
    def is_visual_intent(prompt: str) -> bool:
        """Robust NLP matcher to detect any query requesting an image, diagram, or visual illustration."""
        p = prompt.strip().lower()
        if p.startswith("/image"):
            return True

        if any(p.startswith(cmd) for cmd in [
            "draw", "paint", "sketch", "visualize", "illustrate", "render",
            "generate image", "generate an image", "generate its image", "generate a picture",
            "create image", "create an image", "show image", "show an image", "show picture"
        ]):
            return True

        patterns = [
            r"\b(with|using|having|including)\s+(the\s+)?(help\s+of\s+)?(an?\s+)?(image|picture|diagram|illustration|photo|visual|graphic|chart)\b",
            r"\b(generate|create|draw|make|show|render|provide)\s+(an?|the|its|this|a)\s+(image|picture|diagram|illustration|photo|visual|graphic|chart)\b",
            r"\b(image|picture|diagram|illustration|photo|visual)\s+(of|for|showing|explaining|depicting)\b",
            r"\b(explain|describe|illustrate|show)\b.*\b(image|picture|diagram|illustration|visual)\b",
            r"\b(image|picture|diagram|illustration|visual)\b.*\b(explain|describe|illustrate|show)\b",
            r"\bgenerate\s+its\s+image\b",
            r"\bdraw\s+(this|it|its)\b",
            r"\bpicture\s+of\s+(this|it)\b",
        ]
        return any(re.search(pat, p) for pat in patterns)

    @classmethod
    async def evaluate_routing(
        cls,
        db: AsyncSession,
        request: RouterEvaluationRequest,
        resolved_task: Optional[ResolvedTask] = None
    ) -> RouterEvaluationResponse:
        """
        Routes query to the most capable, available model based on the Authoritative ResolvedTask.
        """
        # 1. Fetch User Settings & System Hardware Profile
        settings_res = await db.execute(select(UserSettings))
        user_settings = settings_res.scalars().first()
        privacy_mode = request.privacy_mode or (user_settings.privacy_mode if user_settings else "HYBRID")

        sys_res = await db.execute(select(SystemProfile).order_by(SystemProfile.created_at.desc()))
        sys_profile = sys_res.scalars().first()
        compute_tier = sys_profile.compute_tier if sys_profile else "Medium"

        # 2. Fetch all registered models
        models_res = await db.execute(select(ModelRegistry))
        models = models_res.scalars().all()

        slug = (request.workspace_slug or "general").lower()

        # 3. Use authoritative ResolvedTask or analyze if not provided
        if resolved_task:
            is_visual = resolved_task.is_visual
            is_coding = request.requires_coding or (resolved_task.domain == "programming") or (resolved_task.intent == "code_generation")
            is_reasoning = request.requires_reasoning or (resolved_task.intent == "deep_reasoning") or (resolved_task.domain == "research")
            is_fast = resolved_task.complexity <= 0.25 and not is_coding and not is_reasoning and not resolved_task.plan.requires_web_search
            detected_intent = resolved_task.intent
            complexity = resolved_task.complexity
        else:
            from backend.app.services.query_intelligence_service import QueryIntelligenceService
            q_analysis = await QueryIntelligenceService.analyze_query(
                user_message=request.prompt,
                workspace_slug=slug
            )
            is_visual = q_analysis.is_visual
            is_coding = request.requires_coding or q_analysis.is_code
            is_reasoning = request.requires_reasoning or q_analysis.is_reasoning
            is_fast = q_analysis.is_fast
            detected_intent = q_analysis.primary_intent
            complexity = q_analysis.complexity

        # Set descriptive routing badge preserving true intent
        if detected_intent == "multimodal_hybrid" or is_visual:
            routing_badge = "🎨 Autonomous Visual Illustration"
        elif is_coding:
            routing_badge = "💻 Qwen Coder Specialist"
        elif is_reasoning:
            routing_badge = "🧠 DeepSeek R1 Step-by-Step Reasoning"
        elif is_fast:
            routing_badge = "⚡ Sub-Second Ultra-Fast Engine"
        elif detected_intent in ["definition", "explanation"]:
            routing_badge = "📖 Concise Universal Knowledge Engine"
        elif detected_intent in ["current_information", "web_search"]:
            routing_badge = "🌐 Live Grounded Search Engine"
        else:
            routing_badge = "⚡ Fast Universal Engine"

        # 4. Check available Ollama installed tags and API keys
        import os
        from backend.app.services.providers.model_manager import model_manager
        installed_tags = await model_manager.ollama.get_installed_tags() if await model_manager.ollama.is_available() else []
        has_cloud_keys = bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("GOOGLE_API_KEY"))

        # Score Candidate Models
        candidate_models: List[Tuple[ModelRegistry, float]] = []
        for m in models:
            # Privacy boundary check
            if privacy_mode == "LOCAL_ONLY" and not m.is_local:
                continue
            if privacy_mode == "CLOUD" and m.is_local:
                continue

            score = 1.0

            # Dynamic check against actual running Ollama tags
            is_installed_in_ollama = m.name in installed_tags or any(m.name.split(":")[0] in t for t in installed_tags)
            if is_installed_in_ollama or m.is_installed:
                score += 15.0

            # If no cloud keys are configured, heavily penalize cloud models
            if not m.is_local and not has_cloud_keys:
                score -= 25.0

            # Match capabilities
            if is_coding and m.coding_capable:
                score += 5.0
            if is_reasoning and m.reasoning_capable:
                score += 5.0
            if is_fast and m.parameters_b <= 4.0:
                score += 4.0

            # Workspace domain alignment
            if "engineering" in slug or "dev" in slug or "software" in slug:
                if m.coding_capable:
                    score += 4.0
            elif "research" in slug or "math" in slug or "science" in slug:
                if m.reasoning_capable:
                    score += 4.0

            # Hardware tier feasibility
            if m.is_local:
                if compute_tier in ["Low", "Minimum"] and m.parameters_b > 4.0:
                    score -= 2.0
                elif compute_tier in ["Ultra", "High"] and m.parameters_b >= 7.0:
                    score += 2.0

            candidate_models.append((m, score))

        candidate_models.sort(key=lambda x: x[1], reverse=True)

        chosen_model = candidate_models[0][0] if candidate_models else None

        if not chosen_model:
            return RouterEvaluationResponse(
                selected_model_id="llama3.2:3b",
                selected_model_name="Llama 3.2 3B",
                execution_mode="local",
                privacy_compliant=True,
                confidence_score=0.9,
                routing_reason="Fast local model selected.",
                complexity_score=complexity,
                detected_intent=detected_intent,
            )

        execution_mode = "local" if chosen_model.is_local else "cloud"
        fallback_id = candidate_models[1][0].name if len(candidate_models) > 1 else None

        return RouterEvaluationResponse(
            selected_model_id=chosen_model.name,
            selected_model_name=chosen_model.display_name,
            execution_mode=execution_mode,
            privacy_compliant=(privacy_mode != "LOCAL_ONLY" or chosen_model.is_local),
            confidence_score=min(0.98, round(0.75 + (complexity * 0.2), 2)),
            routing_reason=f"{routing_badge} • Selected {chosen_model.display_name}",
            complexity_score=round(complexity, 2),
            detected_intent=detected_intent,
            fallback_model_id=fallback_id,
        )
