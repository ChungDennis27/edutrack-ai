"""Runtime LLM settings so a new relay key works without restarting Flask.

The saved file overrides ``.env``. It is gitignored. The API never returns the
full key, and errors are scrubbed before they reach the browser.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from app.services.llm_client import LLMClient

PROVIDERS = ("openai", "anthropic")
_MODEL_RE = re.compile(r"^[\w./:@+-]{1,80}$")


class SettingsError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def settings_path(app_config) -> Path | None:
    raw = app_config.get("LLM_SETTINGS_PATH") or ""
    if not raw:
        return None
    return Path(raw)


def load_saved(path: Path | None) -> dict | None:
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not data.get("api_key"):
        return None
    return data


def effective_llm_config(app_config) -> dict:
    """Saved UI settings win. Otherwise use the environment config."""
    saved = load_saved(settings_path(app_config))
    if saved:
        return {
            "provider": saved.get("provider") or "openai",
            "base_url": saved.get("base_url") or "",
            "model": saved.get("model") or "",
            "api_key": saved.get("api_key") or "",
            "source": "saved",
        }
    return {
        "provider": app_config.get("LLM_PROVIDER") or "openai",
        "base_url": app_config.get("LLM_BASE_URL") or "",
        "model": app_config.get("LLM_MODEL") or "",
        "api_key": app_config.get("LLM_API_KEY") or "",
        "source": "env",
    }


def mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "••••"
    return f"{api_key[:3]}…{api_key[-4:]}"


def public_view(config: dict) -> dict:
    return {
        "provider": config.get("provider") or "openai",
        "base_url": config.get("base_url") or "",
        "model": config.get("model") or "",
        "has_key": bool(config.get("api_key")),
        "key_hint": mask_key(config.get("api_key") or ""),
        "source": config.get("source") or "env",
    }


def _clean_url(value: str, *, required: bool) -> str:
    text = value.strip()
    if not text:
        if required:
            raise SettingsError("請填 Base URL。中轉站通常以 /v1 結尾。")
        return ""
    if len(text) > 300 or any(char in text for char in "\r\n\t "):
        raise SettingsError("Base URL 格式不正確")
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SettingsError("Base URL 必須是 http 或 https 網址")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SettingsError("請把 API key 填在 key 欄，不要放在網址裡")
    if "sk-" in text.lower():
        raise SettingsError("請把 API key 填在 key 欄，不要放在網址裡")
    return text.rstrip("/")


def validate_settings(payload: dict, *, fallback_key: str = "") -> dict:
    if not isinstance(payload, dict):
        raise SettingsError("設定格式不正確")
    provider = payload.get("provider") or "openai"
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise SettingsError("provider 只可以是 openai 或 anthropic")

    model = payload.get("model")
    if not isinstance(model, str) or not _MODEL_RE.match(model.strip()):
        raise SettingsError("請填模型名稱，例如 deepseek-chat 或 gpt-4o-mini")

    base_raw = payload.get("base_url") if payload.get("base_url") is not None else ""
    if not isinstance(base_raw, str):
        raise SettingsError("Base URL 格式不正確")
    base_url = _clean_url(base_raw, required=provider == "openai")

    raw_key = payload.get("api_key")
    if raw_key is None or raw_key == "":
        api_key = fallback_key
    elif not isinstance(raw_key, str):
        raise SettingsError("API key 格式不正確")
    else:
        api_key = raw_key.strip()
    if not api_key:
        raise SettingsError("請填 API key")
    if len(api_key) < 8 or len(api_key) > 400 or any(char in api_key for char in "\r\n\t "):
        raise SettingsError("API key 格式不正確")
    if api_key in base_url:
        raise SettingsError("請把 API key 填在 key 欄，不要放在網址裡")

    return {
        "provider": provider,
        "base_url": base_url,
        "model": model.strip(),
        "api_key": api_key,
        "source": "saved",
    }


def save_settings(path: Path, settings: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            {
                "provider": settings["provider"],
                "base_url": settings["base_url"],
                "model": settings["model"],
                "api_key": settings["api_key"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def reset_settings(path: Path) -> None:
    if path.is_file():
        path.unlink()


def scrub(message: str, secret: str) -> str:
    cleaned = message or "連線失敗"
    if secret:
        cleaned = cleaned.replace(secret, "***")
    cleaned = re.sub(r"sk-[A-Za-z0-9_\-]{6,}", "sk-***", cleaned)
    return cleaned.replace("\n", " ")[:300]


def probe_llm(settings: dict) -> str:
    client = LLMClient(
        api_key=settings["api_key"],
        model=settings["model"],
        base_url=settings["base_url"] or None,
        provider=settings["provider"],
        timeout=20.0,
    )
    if not client.available:
        raise SettingsError("未設定 API key", 503)
    try:
        text = client.complete(
            "回覆 OK",
            system="只回覆 OK，不要加其他字。",
            max_tokens=16,
            temperature=0,
        )
    except Exception as exc:
        raise SettingsError(scrub(str(exc), settings["api_key"]), 502) from None
    reply = (text or "").strip()
    if not reply:
        raise SettingsError("中轉站沒有回覆內容", 502)
    return scrub(reply, settings["api_key"])[:80]
