from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, List, Optional


class BaseModelProvider(ABC):
    """Abstract base class establishing standard interface for all LLM providers."""

    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Generate complete LLM response text."""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """Stream LLM response tokens."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check whether provider is reachable and operational."""
        pass

    @abstractmethod
    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Return specifications and capabilities for the given model."""
        pass

    def supports_tools(self) -> bool:
        """Indicate whether provider supports native function/tool calling."""
        return True

    def supports_vision(self) -> bool:
        """Indicate whether provider supports multimodal image inputs."""
        return False

    def supports_context(self, context_length: int) -> bool:
        """Check if provider/model supports the requested context length."""
        return context_length <= 8192

    async def cancel(self, task_id: str) -> bool:
        """Cancel an ongoing generation request if supported."""
        return True
