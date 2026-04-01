"""
LLM Provider abstraction layer.
Factory function routes to OpenRouter, Anthropic, or LM Studio providers.
"""
from __future__ import annotations

from .base import (
    CompletionResult,
    LLMProvider,
    Message,
    ModelConfig,
    StreamEvent,
    ToolCall,
    ToolDef,
    UsageInfo,
)

# Provider registry — lazy imports to avoid hard deps
_PROVIDER_REGISTRY: dict[str, str] = {
    "openrouter": "OpenRouterProvider",
    "anthropic": "AnthropicProvider",
    "lmstudio": "LMStudioProvider",
}


def get_provider(name: str, model_id: str = "", **kwargs) -> LLMProvider:
    """
    Factory function to get a provider instance.

    Args:
        name: Provider name ("openrouter", "anthropic", "lmstudio")
        model_id: Model identifier (e.g., "minimax/minimax-m2.7")
        **kwargs: Extra arguments passed to provider constructor
    """
    name = name.lower().strip()

    if name == "openrouter":
        from .openrouter import OpenRouterProvider
        return OpenRouterProvider(model_id=model_id, **kwargs)
    elif name == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(model_id=model_id, **kwargs)
    elif name == "lmstudio":
        from .lmstudio import LMStudioProvider
        return LMStudioProvider(model_id=model_id, **kwargs)
    else:
        raise ValueError(
            f"Unknown provider '{name}'. Available: {', '.join(_PROVIDER_REGISTRY)}"
        )


__all__ = [
    "get_provider",
    "LLMProvider",
    "Message",
    "ToolCall",
    "ToolDef",
    "CompletionResult",
    "StreamEvent",
    "UsageInfo",
    "ModelConfig",
]
