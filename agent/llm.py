import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
import litellm

load_dotenv()


@dataclass
class LLMConfig:
    api_base: str = field(default_factory=lambda: os.getenv("LLM_API_BASE", ""))
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "openai/gpt-4o"))
    temperature: float = 0.7
    max_tokens: int = 1024

    def validate(self):
        missing = []
        if not self.api_key:
            missing.append("LLM_API_KEY")
        if not self.model:
            missing.append("LLM_MODEL")
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")


_config: LLMConfig | None = None


def get_config() -> LLMConfig:
    global _config
    if _config is None:
        _config = LLMConfig()
        _config.validate()
    return _config


def configure(
    api_base: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLMConfig:
    global _config
    _config = LLMConfig(
        api_base=api_base or os.getenv("LLM_API_BASE", ""),
        api_key=api_key or os.getenv("LLM_API_KEY", ""),
        model=model or os.getenv("LLM_MODEL", "openai/gpt-4o"),
        temperature=temperature if temperature is not None else 0.7,
        max_tokens=max_tokens if max_tokens is not None else 1024,
    )
    _config.validate()
    return _config


def _resolve_model(model: str, api_base: str) -> str:
    if "/" in model:
        return model
    if api_base:
        return f"openai/{model}"
    return model


def _build_kwargs(config: LLMConfig, **overrides) -> dict:
    model = _resolve_model(config.model, config.api_base)
    kwargs: dict = {
        "model": model,
        "temperature": overrides.pop("temperature", config.temperature),
        "max_tokens": overrides.pop("max_tokens", config.max_tokens),
    }
    if config.api_base:
        kwargs["api_base"] = config.api_base
    if config.api_key:
        kwargs["api_key"] = config.api_key
    kwargs.update(overrides)
    return kwargs


def chat(
    messages: list[dict],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    stream: bool = False,
    **extra,
) -> litellm.ModelResponse:
    config = get_config()
    overrides: dict = {}
    if temperature is not None:
        overrides["temperature"] = temperature
    if max_tokens is not None:
        overrides["max_tokens"] = max_tokens
    if tools:
        overrides["tools"] = tools
    if tool_choice:
        overrides["tool_choice"] = tool_choice
    if stream:
        overrides["stream"] = stream
    overrides.update(extra)

    kwargs = _build_kwargs(config, **overrides)
    return litellm.completion(messages=messages, **kwargs)


def chat_stream(
    messages: list[dict],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict] | None = None,
    **extra,
):
    config = get_config()
    overrides: dict = {"stream": True}
    if temperature is not None:
        overrides["temperature"] = temperature
    if max_tokens is not None:
        overrides["max_tokens"] = max_tokens
    if tools:
        overrides["tools"] = tools
    overrides.update(extra)

    kwargs = _build_kwargs(config, **overrides)
    return litellm.completion(messages=messages, **kwargs)
