"""Provider-agnostic LLM client.

Supports any OpenAI-compatible endpoint (e.g. TeamoRouter, DeepSeek, OpenAI,
Groq, Together) via ``base_url``, and Anthropic's native API as a fallback.

Configure through the Flask config:
    LLM_PROVIDER = "openai" | "anthropic"
    LLM_API_KEY  = "<key>"
    LLM_BASE_URL = "https://api.teamorouter.com/v1"  # only for openai provider
    LLM_MODEL    = "deepseek-flash-free"
"""
from __future__ import annotations

import json
import logging
import re
from typing import Iterator

logger = logging.getLogger(__name__)


class LLMNotConfigured(RuntimeError):
    """Raised when no API key is configured."""


def extract_json(text: str) -> dict:
    """Parse JSON from an LLM response, tolerating ```json fences and prose."""
    if not text:
        raise ValueError("LLM returned an empty response")

    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z0-9]*\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate).strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start != -1 and end > start:
            return json.loads(candidate[start : end + 1])
        raise


class LLMClient:
    """Thin wrapper exposing a uniform ``complete`` / ``stream`` interface."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        provider: str = "openai",
        timeout: float = 90.0,
    ):
        self.model = model
        self.provider = provider
        self.available = bool(api_key)
        self._client = None

        if not self.available:
            return

        if provider == "anthropic":
            from anthropic import Anthropic

            self._client = Anthropic(api_key=api_key, timeout=timeout)
        else:
            from openai import OpenAI

            kwargs: dict = {"api_key": api_key, "timeout": timeout}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = OpenAI(**kwargs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dialog(self, history: list[dict] | None, user: str) -> list[dict]:
        """Prior turns plus the current user message. System is added separately."""
        messages: list[dict] = []
        for item in history or []:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role not in ("user", "assistant") or not isinstance(content, str) or not content:
                continue
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user})
        return messages

    def _build_messages(
        self,
        system: str | None,
        user: str,
        history: list[dict] | None = None,
    ) -> list[dict]:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(self._dialog(history, user))
        return messages

    def complete(
        self,
        user: str,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        json_mode: bool = False,
        history: list[dict] | None = None,
    ) -> str:
        """Single-shot completion, returns the raw text response."""
        if not self._client:
            raise LLMNotConfigured("LLM API key not configured")

        dialog = self._dialog(history, user)

        if self.provider == "anthropic":
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or "",
                messages=dialog,
            )
            return resp.content[0].text

        kwargs: dict = {
            "model": self.model,
            "messages": self._build_messages(system, user, history),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            try:
                resp = self._client.chat.completions.create(
                    **kwargs, response_format={"type": "json_object"}
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:  # provider may not support json_object
                logger.warning("json_mode unsupported, retrying without it: %s", exc)

        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def stream(
        self,
        user: str,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        history: list[dict] | None = None,
    ) -> Iterator[str]:
        """Yield text deltas from a streaming completion."""
        if not self._client:
            raise LLMNotConfigured("LLM API key not configured")

        dialog = self._dialog(history, user)

        if self.provider == "anthropic":
            with self._client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or "",
                messages=dialog,
            ) as stream:
                for text in stream.text_stream:
                    yield text
            return

        stream = self._client.chat.completions.create(
            model=self.model,
            messages=self._build_messages(system, user, history),
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield content


def build_llm_client(app_config, temperature_note: str | None = None) -> LLMClient:
    """Factory reading the Flask config mapping."""
    return LLMClient(
        api_key=app_config.get("LLM_API_KEY", ""),
        model=app_config.get("LLM_MODEL", "deepseek-flash-free"),
        base_url=app_config.get("LLM_BASE_URL") or None,
        provider=app_config.get("LLM_PROVIDER", "openai"),
    )
