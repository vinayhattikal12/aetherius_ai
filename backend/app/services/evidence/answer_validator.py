import re
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel
from backend.app.core.logging import logger


class ClaimEvaluation(BaseModel):
    claim_text: str
    verdict: str  # "SUPPORTED", "UNSUPPORTED", "CONTRADICTED", "UNCERTAIN"
    confidence: float
    matched_evidence_snippet: Optional[str] = None


class ValidationReport(BaseModel):
    is_valid: bool
    grounding_score: float
    constraints_satisfied: bool
    citations_valid: bool
    claims_evaluated: List[ClaimEvaluation] = []
    unsupported_claims_count: int = 0
    issues: List[str] = []
    warnings: List[str] = []
    repair_instruction: Optional[str] = None


class AnswerValidationEngine:
    """
    Production-grade Pre-Generation Answer Validation, Claim-Level Factual Verification,
    Anti-Hallucination Guardrails, and Automated Response Repair Engine.
    """

    @classmethod
    def extract_claims(cls, text: str) -> List[str]:
        """Extracts discrete factual assertions, numerical claims, dates, and entity assignments."""
        if not text:
            return []

        # Remove code blocks, markdown tables, and headers to focus on prose assertions
        cleaned = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        cleaned = re.sub(r"\|.*?\|", "", cleaned)
        cleaned = re.sub(r"^#+\s+.*$", "", cleaned, flags=re.MULTILINE)

        sentences = re.split(r"(?<=[.!?])\s+", cleaned.strip())
        claims = []
        for s in sentences:
            s_clean = s.strip()
            if len(s_clean) < 15 or len(s_clean) > 280:
                continue
            # Look for factual indicators (verbs, numbers, dates, named roles)
            if re.search(r"(\b\d{2,4}\b|\b\d+(\.\d+)?%?\b|is the|was the|served as|released in|founded in|launched in|headquartered in|won the|score was)", s_clean, flags=re.IGNORECASE):
                claims.append(s_clean)

        return claims[:8]  # Bound to top 8 prominent claims for fast sub-millisecond evaluation

    @classmethod
    def evaluate_claims(cls, claims: List[str], evidence_chunks: List[str]) -> Tuple[List[ClaimEvaluation], List[str]]:
        """Evaluates extracted claims against retrieved evidence chunks."""
        if not claims or not evidence_chunks:
            return [], []

        evidence_text = " ".join(evidence_chunks).lower()
        evaluations: List[ClaimEvaluation] = []
        issues: List[str] = []

        stop_words = {"the", "a", "an", "is", "was", "are", "were", "and", "or", "in", "on", "at", "to", "for", "with", "by", "that", "this"}

        for claim in claims:
            c_words = [w for w in re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", claim.lower()) if w not in stop_words]
            if not c_words:
                continue

            matches = [w for w in c_words if w in evidence_text]
            match_ratio = len(matches) / len(c_words)

            # Check specific numbers/dates in claim
            numbers_in_claim = re.findall(r"\b\d{2,4}\b", claim)
            numbers_matched = all(n in evidence_text for n in numbers_in_claim) if numbers_in_claim else True

            if match_ratio >= 0.65 and numbers_matched:
                verdict = "SUPPORTED"
                conf = round(min(1.0, match_ratio), 2)
            elif match_ratio >= 0.35:
                verdict = "UNCERTAIN"
                conf = 0.5
            else:
                verdict = "UNSUPPORTED"
                conf = 0.2
                issues.append(f"Claim unsupported by verified evidence: '{claim[:100]}...'")

            evaluations.append(ClaimEvaluation(
                claim_text=claim,
                verdict=verdict,
                confidence=conf
            ))

        return evaluations, issues

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

        stop_words = {
            "this", "that", "these", "those", "have", "with", "from", "which", "will", "would",
            "could", "should", "there", "their", "about", "using", "into", "more", "other"
        }
        factual_words = [w for w in response_words if w not in stop_words]
        if not factual_words:
            return 1.0

        matches = sum(1 for w in factual_words if w in evidence_text)
        overlap_ratio = matches / len(factual_words)

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
        """Performs full pre-flight audit and claim-level verification on synthesized response."""
        active_constraints = constraints or {}
        sources = available_sources or []
        chunks = evidence_chunks or []

        c_ok, c_issues = cls.validate_constraints(response_text, active_constraints)
        cit_ok, cit_issues = cls.validate_citations(response_text, len(sources))
        leak_ok, leak_issues = cls.validate_leakage(response_text)
        grounding = cls.calculate_grounding_score(response_text, chunks)

        # Claim-level validation if external evidence was provided
        claims = cls.extract_claims(response_text) if chunks else []
        claim_evals, claim_issues = cls.evaluate_claims(claims, chunks) if chunks and len(chunks) > 0 else ([], [])

        all_issues = c_issues + cit_issues + leak_issues + (claim_issues if grounding < 0.40 else [])
        is_valid = len(all_issues) == 0

        repair_instruction = None
        if not is_valid:
            repair_instruction = (
                "CRITICAL CORRECTION REQUIRED:\n"
                "Your previous response failed validation with the following issues:\n"
                + "\n".join(f"- {issue}" for issue in all_issues)
                + "\nPlease regenerate the response strictly fixing these violations while preserving factual accuracy."
            )

        return ValidationReport(
            is_valid=is_valid,
            grounding_score=grounding,
            constraints_satisfied=c_ok,
            citations_valid=cit_ok,
            claims_evaluated=claim_evals,
            unsupported_claims_count=sum(1 for c in claim_evals if c.verdict == "UNSUPPORTED"),
            issues=all_issues,
            warnings=[],
            repair_instruction=repair_instruction
        )
