from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .models import ReviewPrompt
from .prompting import SYSTEM_PROMPT, build_prompt


@dataclass(slots=True)
class ProviderSettings:
    provider: str
    api_key: str
    model: str
    base_url: str | None = None
    preferred_api: str = "responses"


@dataclass(slots=True)
class ProviderDefinition:
    provider: str
    api_key_env: str
    base_url_env: str | None
    model_env: str | None
    default_model: str
    preferred_api: str = "responses"


PROVIDERS: dict[str, ProviderDefinition] = {
    "deepseek": ProviderDefinition(
        provider="deepseek",
        api_key_env="DEEPSEEK_API_KEY",
        base_url_env="DEEPSEEK_BASE_URL",
        model_env="DEEPSEEK_CODER_MODEL",
        default_model="deepseek-coder",
        preferred_api="chat_completions",
    ),
    "bcp": ProviderDefinition(
        provider="bcp",
        api_key_env="BCP_API_KEY",
        base_url_env="BCP_BASE_URL",
        model_env="BCP_CODER_MODEL",
        default_model="bcp-coder",
        preferred_api="chat_completions",
    ),
    "openai": ProviderDefinition(
        provider="openai",
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
        model_env="OPENAI_CODER_MODEL",
        default_model="gpt-4.1-mini",
    ),
}


def resolve_provider_settings(
    provider_name: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> ProviderSettings:
    normalized = (provider_name or "deepseek").strip().lower()
    definition = PROVIDERS.get(normalized)
    if definition is None:
        raise RuntimeError(
            f"Unsupported provider '{provider_name}'. Supported providers: {', '.join(sorted(PROVIDERS))}."
        )

    resolved_api_key = (api_key or "").strip() or os.environ.get(definition.api_key_env, "").strip()
    if not resolved_api_key:
        raise RuntimeError(
            f"Missing API key for provider '{normalized}'. Set the action input 'api_key' or env '{definition.api_key_env}'."
        )

    resolved_model = (model or "").strip()
    if not resolved_model and definition.model_env:
        resolved_model = os.environ.get(definition.model_env, "").strip()
    if not resolved_model:
        resolved_model = definition.default_model

    resolved_base_url = (base_url or "").strip() or None
    if resolved_base_url is None and definition.base_url_env:
        env_base_url = os.environ.get(definition.base_url_env, "").strip()
        resolved_base_url = env_base_url or None

    return ProviderSettings(
        provider=normalized,
        api_key=resolved_api_key,
        model=resolved_model,
        base_url=resolved_base_url,
        preferred_api=definition.preferred_api,
    )


class ProviderAdapter(ABC):
    @abstractmethod
    def review(self, prompt: ReviewPrompt) -> str:
        raise NotImplementedError


class OpenAIProvider(ProviderAdapter):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        preferred_api: str = "responses",
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - environment specific
            raise RuntimeError(
                "openai package is not installed. Install requirements.txt from the action directory."
            ) from exc

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._preferred_api = preferred_api

    def _review_via_responses(self, user_prompt: str) -> str:
        response = self._client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = getattr(response, "output_text", None)
        if text:
            return str(text)
        output = getattr(response, "output", [])
        texts: list[str] = []
        for item in output:
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", "") == "output_text":
                    texts.append(getattr(content, "text", ""))
        return "\n".join(texts)

    def _review_via_chat_completions(self, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        choices = getattr(response, "choices", []) or []
        texts: list[str] = []
        for choice in choices:
            message = getattr(choice, "message", None)
            content = getattr(message, "content", None)
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        texts.append(str(item.get("text", "")))
                    else:
                        text_value = getattr(item, "text", None)
                        if text_value:
                            texts.append(str(text_value))
        return "\n".join(texts)

    def review(self, prompt: ReviewPrompt) -> str:
        user_prompt = build_prompt(
            pr_title=prompt.pr.title,
            pr_body=prompt.pr.body,
            chunk=prompt.chunk,
            repo_context=prompt.repo_context,
            policy_summary=prompt.policy_summary,
            review_language=getattr(prompt, "review_language", "en"),
        )
        if self._preferred_api == "chat_completions":
            return self._review_via_chat_completions(user_prompt)
        try:
            return self._review_via_responses(user_prompt)
        except Exception as exc:
            if exc.__class__.__name__ != "NotFoundError":
                raise
            return self._review_via_chat_completions(user_prompt)


class UnsupportedProvider(ProviderAdapter):
    def __init__(self, provider: str) -> None:
        self.provider = provider

    def review(self, prompt: ReviewPrompt) -> str:
        raise NotImplementedError(f"Provider '{self.provider}' is not implemented yet")
