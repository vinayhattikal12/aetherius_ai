import re
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel
from backend.app.core.logging import logger


class ValidationReport(BaseModel):
    is_valid: bool
    grounding_score: float
    constraints_satisfied: bool
    citations_valid: bool
    issues: List[str] = []
    warnings: List[str] = []
    repair_instruction: Optional[str] = None


class AnswerValidationEngine:
    """
    Production-grade Pre-Generation Answer Validation, Anti-Hallucination Guardrails,
    and Automated Response Repair Engine.
    """

    @classmethod
    def validate_constraints(
        cls,
        text: str,
        constraints: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Checks whether the generated response honors all accumulated user constraints."""
        issues = []
        lower = text.lower()

        # Format constraint
        if constraints.get("format") == "table":
            if "|" not in text or "---" not in text:
                issues.append("Missing required Markdown table format requested by user.")
        elif constraints.get("format") == "json":
            if "{" not in text or "}" not in text:
                issues.append("Missing required JSON formatted output requested by user.")
        elif constraints.get("format") == "bullet_points":
            if not any(line.strip().startswith(("-", "*", "•")) for line in text.split("\n")):
                issues.append("Missing required bullet point structure requested by user.")

        # Language constraint
        lang = constraints.get("language")
        if lang:
            if "```" in text:
                code_matches = re.findall(r"```([a-zA-Z0-9_\-\+]+)", text)
                if code_matches:
                    normalized_codes = [c.lower() for c in code_matches]
                    target_lang = "python" if lang in ["py", "python"] else "rust" if lang == "rust" else "golang" if lang in ["go", "golang"] else lang
                    if not any(target_lang in c for c in normalized_codes):
                        issues.append(f"Code block was not provided in requested language '{lang}'.")

        return len(issues) == 0, issues

    @classmethod
    def validate_citations(
        cls,
        text: str,
        num_sources: int
    ) -> Tuple[bool, List[str]]:
        """Verifies that all inline footnote numbers like [1], [2] correspond to valid source indices."""
        issues = []
        if num_sources == 0:
            # If no external sources are available, ensure there are no phantom [1], [2] references
            phantom = re.findall(r"\[(\d+)\]", text)
            if phantom:
                issues.append(f"Response contains citation footnotes {phantom} but no external sources were retrieved.")
            return len(issues) == 0, issues

        cited_indices = re.findall(r"\[(\d+)\]", text)
        for idx_str in cited_indices:
            idx = int(idx_str)
            if idx < 1 or idx > num_sources:
                issues.append(f"Invalid source footnote [{idx}]: Only {num_sources} sources available.")

        return len(issues) == 0, issues

    @classmethod
    def calculate_grounding_score(
        cls,
        response_text: str,
        evidence_chunks: List[str]
    ) -> float:
        """Measures lexical and semantic keyword overlap between response assertions and retrieved evidence."""
        if not evidence_chunks or not response_text:
            return 1.0  # Default neutral score if no external evidence was required

        evidence_text = " ".join(evidence_chunks).lower()
        response_words = set(re.findall(r"\b[a-zA-Z0-9_\-]{4,}\b", response_text.lower()))

        if not response_words:
            return 1.0

        # Stop words removal for factual grounding evaluation
        stop_words = {
            "this", "that", "these", "those", "have", "with", "from", "which", "will", "would",
            "could", "should", "there", "their", "about", "using", "into", "more", "other"
        }
        factual_words = [w for w in response_words if w not in stop_words]
        if not factual_words:
            return 1.0

        matches = sum(1 for w in factual_words if w in evidence_text)
        overlap_ratio = matches / len(factual_words)

        # Scale to calibrated grounding confidence score (0.0 - 1.0)
        return round(min(1.0, max(0.2, overlap_ratio * 1.5)), 2)

    @classmethod
    def validate_leakage(cls, text: str) -> Tuple[bool, List[str]]:
        """Checks for accidental leakage of internal system prompts, brackets, or memory headers."""
        issues = []
        forbidden_markers = [
            "[CONVERSATION CONTEXT",
            "[ENVIRONMENT & USER CONTEXT",
            "[USER PROFILE &",
            "[AVAILABLE SANDBOX TOOLS",
            "[LIVE WEB SEARCH RESULTS",
            "[USER CONSTRAINTS",
            "search.aetherius.ai",
            "Active Conversation Topic:",
            "Turn Relation Mode:"
        ]
        for marker in forbidden_markers:
            if marker.lower() in text.lower():
                issues.append(f"Response contains internal system diagnostic marker '{marker}'.")
        return len(issues) == 0, issues

    @classmethod
    def validate_response(
        cls,
        response_text: str,
        constraints: Optional[Dict[str, Any]] = None,
        available_sources: Optional[List[Dict[str, Any]]] = None,
        evidence_chunks: Optional[List[str]] = None
    ) -> ValidationReport:
        """Performs full pre-flight audit on synthesized response."""
        active_constraints = constraints or {}
        sources = available_sources or []
        chunks = evidence_chunks or []

        c_ok, c_issues = cls.validate_constraints(response_text, active_constraints)
        cit_ok, cit_issues = cls.validate_citations(response_text, len(sources))
        leak_ok, leak_issues = cls.validate_leakage(response_text)
        grounding = cls.calculate_grounding_score(response_text, chunks)

        all_issues = c_issues + cit_issues + leak_issues
        is_valid = len(all_issues) == 0

        repair_instruction = None
        if not is_valid:
            repair_instruction = (
                "CRITICAL CORRECTION REQUIRED:\n"
                "Your previous response failed validation with the following issues:\n"
                + "\n".join(f"- {issue}" for issue in all_issues)
                + "\nPlease regenerate the response strictly fixing these violations while preserving accuracy."
            )

        return ValidationReport(
            is_valid=is_valid,
            grounding_score=grounding,
            constraints_satisfied=c_ok,
            citations_valid=cit_ok,
            issues=all_issues,
            warnings=[],
            repair_instruction=repair_instruction
        )
