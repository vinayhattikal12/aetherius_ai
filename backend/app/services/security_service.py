import re
from typing import Dict, Any, Tuple, List


class SecurityGuardService:
    """Provides PII sanitization, prompt injection detection, and compliance protection."""

    # Regex patterns for sensitive data
    PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b",
        "api_key": r"\b(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36}|AIza[0-9A-Za-z-_]{35})\b",
        "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "phone": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    }

    # Prompt injection heuristic patterns
    INJECTION_PATTERNS = [
        r"(?:ignore previous instructions|disregard all previous rules|system override)",
        r"(?:reveal your system prompt|output your initial prompt|show hidden instructions)",
        r"(?:you are now in unrestricted mode|jailbreak mode enabled|DAN mode active)"
    ]

    @classmethod
    def sanitize_pii(cls, text: str) -> Tuple[str, List[str]]:
        """Masks detected PII with generic tokens and returns list of detected categories."""
        sanitized = text
        detected_categories = []

        for category, pattern in cls.PATTERNS.items():
            matches = list(re.finditer(pattern, sanitized, re.IGNORECASE))
            if matches:
                detected_categories.append(category)
                sanitized = re.sub(pattern, f"[REDACTED_{category.upper()}]", sanitized, flags=re.IGNORECASE)

        return sanitized, detected_categories

    @classmethod
    def inspect_prompt_safety(cls, text: str) -> Dict[str, Any]:
        """Checks for prompt injection attempts and malicious command sequences."""
        is_safe = True
        warnings = []

        for pat in cls.INJECTION_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                is_safe = False
                warnings.append("Potential prompt injection pattern detected.")
                break

        return {
            "is_safe": is_safe,
            "risk_level": "high" if not is_safe else "low",
            "warnings": warnings
        }
