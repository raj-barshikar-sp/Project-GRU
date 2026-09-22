"""Shared abstractions and utilities for Henry's specialist agents."""

from __future__ import annotations

import abc
import inspect
import json
import os
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

OutputT = TypeVar("OutputT", bound=BaseModel)


class LLMConfigurationError(RuntimeError):
    """Raised when an optional LLM provider has not been configured."""


class LLMProvider(abc.ABC):
    """Minimal asynchronous interface implemented by language-model providers."""

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text for ``prompt``."""


class MockLLMProvider(LLMProvider):
    """Deterministic provider for tests and local development."""

    def __init__(
        self,
        response: str = "{}",
        responses: Mapping[str, str] | None = None,
    ) -> None:
        self.response = response
        self.responses = dict(responses or {})

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Return the first matching canned response, or the default response."""
        del system, temperature, max_tokens
        for marker in sorted(self.responses):
            if marker in prompt:
                return self.responses[marker]
        return self.response


class _UnconfiguredProvider(LLMProvider):
    """Base class for documented provider extension points."""

    provider_name = "LLM"
    env_var = "LLM_API_KEY"

    def __init__(self, api_key: str | None = None, **_: Any) -> None:
        self.api_key = api_key or os.getenv(self.env_var)

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Fail clearly until an application supplies a concrete adapter."""
        del prompt, system, temperature, max_tokens
        if not self.api_key:
            raise LLMConfigurationError(
                f"{self.provider_name} is not configured; set {self.env_var} "
                "and install a concrete provider adapter."
            )
        raise LLMConfigurationError(
            f"{self.provider_name} credentials were found, but this package only "
            "defines the provider interface. Inject a concrete LLMProvider."
        )


class OpenAIProvider(_UnconfiguredProvider):
    """Optional OpenAI provider placeholder."""

    provider_name = "OpenAI"
    env_var = "OPENAI_API_KEY"


class AnthropicProvider(_UnconfiguredProvider):
    """Optional Anthropic provider placeholder."""

    provider_name = "Anthropic"
    env_var = "ANTHROPIC_API_KEY"


class BaseAgent(Generic[OutputT]):
    """Base class that supplies a language-model provider to specialist agents."""

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self.llm = llm or MockLLMProvider()


def value(source: Any, *names: str, default: Any = None) -> Any:
    """Read the first present field from a mapping or model-like object."""
    if source is None:
        return default
    for name in names:
        if isinstance(source, Mapping) and name in source:
            return source[name]
        if hasattr(source, name):
            return getattr(source, name)
    return default


def text_value(source: Any, *names: str, default: str = "") -> str:
    """Read the first present field from ``source`` as a stripped string."""
    raw = value(source, *names, default=None)
    if raw is None:
        return default
    rendered = str(raw).strip()
    return rendered or default


def number_value(source: Any, *names: str, default: float = 0.0) -> float:
    """Read the first present field from ``source`` as a float."""
    raw = value(source, *names, default=None)
    if raw is None or isinstance(raw, bool):
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def int_value(source: Any, *names: str, default: int = 0) -> int:
    """Read the first present field from ``source`` as an int."""
    return int(number_value(source, *names, default=float(default)))


def bool_value(source: Any, *names: str) -> bool:
    """Read the first present field from ``source`` as a boolean."""
    return bool(value(source, *names, default=False))


def items_value(source: Any, *names: str) -> tuple[Any, ...]:
    """Read the first present field from ``source`` as a tuple of items."""
    raw = value(source, *names, default=None)
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes, Mapping)):
        return (raw,)
    if isinstance(raw, Iterable):
        return tuple(raw)
    return (raw,)


def string_values(source: Any, *names: str) -> tuple[str, ...]:
    """Read the first present field from ``source`` as de-duplicated strings."""
    cleaned = [str(item).strip() for item in items_value(source, *names)]
    return tuple(dict.fromkeys(item for item in cleaned if item))


def format_money(amount: float) -> str:
    """Render ``amount`` as whole US dollars with thousands separators."""
    return f"${amount:,.0f}"


def format_money_compact(amount: float) -> str:
    """Render ``amount`` compactly, for example ``$4.85B``."""
    for suffix, size in (("B", 1_000_000_000.0), ("M", 1_000_000.0), ("K", 1_000.0)):
        if abs(amount) >= size:
            scaled = f"{amount / size:,.2f}".rstrip("0").rstrip(".")
            return f"${scaled}{suffix}"
    return format_money(amount)


def model_dump(model: Any) -> dict[str, Any]:
    """Convert Pydantic models, dataclasses, or mappings to a dictionary."""
    if isinstance(model, Mapping):
        return dict(model)
    if hasattr(model, "model_dump"):
        return dict(model.model_dump())
    if hasattr(model, "dict"):
        return dict(model.dict())
    if hasattr(model, "__dict__"):
        return dict(vars(model))
    return {"value": model}


def validate_output(model_type: type[OutputT], payload: Mapping[str, Any]) -> OutputT:
    """Validate ``payload`` with either Pydantic v1 or v2."""
    validator = getattr(model_type, "model_validate", None)
    if validator:
        return validator(payload)
    return model_type.parse_obj(payload)


def parse_json_output(model_type: type[OutputT], text: str) -> OutputT:
    """Parse a JSON object from an LLM response into a typed model."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[-1].rsplit("```", 1)[0]
    start, end = candidate.find("{"), candidate.rfind("}")
    if start < 0 or end < start:
        raise ValueError("LLM response did not contain a JSON object")
    return validate_output(model_type, json.loads(candidate[start : end + 1]))


async def invoke_tool(tool: Any, method_names: tuple[str, ...], **kwargs: Any) -> Any:
    """Invoke the first supported tool method, accommodating sync test doubles."""
    if tool is None:
        return None
    callable_obj: Callable[..., Any] | None = None
    for name in method_names:
        candidate = getattr(tool, name, None)
        if callable(candidate):
            callable_obj = candidate
            break
    if callable_obj is None and callable(tool):
        callable_obj = tool
    if callable_obj is None:
        raise AttributeError(f"{type(tool).__name__} supports none of: {', '.join(method_names)}")
    try:
        result = callable_obj(**kwargs)
    except TypeError:
        result = callable_obj(*kwargs.values())
    if inspect.isawaitable(result):
        return await result
    return result
