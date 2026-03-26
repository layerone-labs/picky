from __future__ import annotations

from abc import ABC, abstractmethod

from .models import ReviewPrompt
from .prompting import SYSTEM_PROMPT, build_prompt


class ProviderAdapter(ABC):
    @abstractmethod
    def review(self, prompt: ReviewPrompt) -> str:
        raise NotImplementedError


class OpenAIProvider(ProviderAdapter):
    def __init__(self, api_key: str, model: str) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - environment specific
            raise RuntimeError(
                "openai package is not installed. Install requirements.txt from the action directory."
            ) from exc

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def review(self, prompt: ReviewPrompt) -> str:
        user_prompt = build_prompt(
            pr_title=prompt.pr.title,
            pr_body=prompt.pr.body,
            chunk=prompt.chunk,
            repo_context=prompt.repo_context,
            policy_summary=prompt.policy_summary,
        )
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


class UnsupportedProvider(ProviderAdapter):
    def __init__(self, provider: str) -> None:
        self.provider = provider

    def review(self, prompt: ReviewPrompt) -> str:
        raise NotImplementedError(f"Provider '{self.provider}' is not implemented yet")
