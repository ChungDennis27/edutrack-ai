"""LLM settings UI must not echo the key, and a saved relay must win over .env."""
import json
from unittest.mock import patch

import pytest
from sqlalchemy.pool import StaticPool

from app import create_app, db
from app.config import DevelopmentConfig, config_by_name
from app.models import User
from app.services.llm_client import build_llm_client
from app.services.llm_settings import SettingsError, probe_llm, validate_settings

SECRET = "relay-key-12345678"


class _SqliteTestConfig(DevelopmentConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }


def test_validate_rejects_key_in_url_and_blank_key():
    with pytest.raises(SettingsError):
        validate_settings(
            {
                "provider": "openai",
                "base_url": "https://user:secret@relay.example/v1",
                "model": "demo-model",
                "api_key": SECRET,
            }
        )
    with pytest.raises(SettingsError):
        validate_settings(
            {
                "provider": "openai",
                "base_url": "file:///tmp/key",
                "model": "demo-model",
                "api_key": SECRET,
            }
        )
    with pytest.raises(SettingsError):
        validate_settings(
            {"provider": "openai", "base_url": "https://relay.example/v1", "model": "demo-model"}
        )


def test_probe_scrubs_the_key():
    with patch("app.services.llm_settings.LLMClient") as client_cls:
        client_cls.return_value.available = True
        client_cls.return_value.complete.side_effect = RuntimeError(f"bad key {SECRET}")
        with pytest.raises(SettingsError) as caught:
            probe_llm(
                {
                    "provider": "openai",
                    "base_url": "https://relay.example/v1",
                    "model": "demo-model",
                    "api_key": SECRET,
                }
            )
    assert SECRET not in caught.value.message
    assert caught.value.status == 502


@pytest.fixture
def app(tmp_path):
    config_by_name["testing"] = _SqliteTestConfig
    try:
        application = create_app("testing")
    finally:
        config_by_name.pop("testing", None)
    application.config["TESTING"] = True
    application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    application.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }
    application.config["LLM_SETTINGS_PATH"] = str(tmp_path / "llm_settings.json")
    application.config["LLM_API_KEY"] = "env-key-abcdefgh"
    application.config["LLM_BASE_URL"] = "https://env.example/v1"
    application.config["LLM_MODEL"] = "env-model"
    application.config["LLM_PROVIDER"] = "openai"
    with application.app_context():
        db.engine.dispose()
        from sqlalchemy import create_engine

        db._app_engines[application][None] = create_engine(
            application.config["SQLALCHEMY_DATABASE_URI"],
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        db.create_all()
        user = User(email="a@example.com", username="student_a", display_name="A")
        user.set_password("password-a")
        db.session.add(user)
        db.session.commit()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "a@example.com", "password": "password-a"},
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    csrf = client.get_cookie("csrf_access_token")
    assert csrf is not None
    return {"X-CSRF-TOKEN": csrf.value}


def test_save_masks_key_and_overrides_env(client, app):
    headers = _login(client)
    saved = client.put(
        "/api/settings/llm",
        json={
            "provider": "openai",
            "base_url": "https://relay.example/v1",
            "model": "relay-model",
            "api_key": SECRET,
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.get_data(as_text=True)
    body = saved.get_json()
    raw = saved.get_data(as_text=True)
    assert SECRET not in raw
    assert body["source"] == "saved"
    assert body["base_url"] == "https://relay.example/v1"
    assert body["model"] == "relay-model"
    assert body["has_key"] is True
    assert body["key_hint"].endswith("5678")

    kept = client.put(
        "/api/settings/llm",
        json={
            "provider": "openai",
            "base_url": "https://relay.example/v1/",
            "model": "relay-model",
            "api_key": "",
        },
        headers=headers,
    )
    assert kept.status_code == 200
    assert SECRET not in kept.get_data(as_text=True)
    on_disk = json.loads((app.config["LLM_SETTINGS_PATH"] and open(app.config["LLM_SETTINGS_PATH"], encoding="utf-8").read()))
    assert on_disk["api_key"] == SECRET
    assert on_disk["base_url"] == "https://relay.example/v1"

    with app.app_context():
        built = build_llm_client(app.config)
    assert built.model == "relay-model"
    assert str(built._client.base_url).startswith("https://relay.example/v1")
    assert built._client.api_key == SECRET


def test_bad_url_and_reset(client, app):
    headers = _login(client)
    bad = client.put(
        "/api/settings/llm",
        json={
            "provider": "openai",
            "base_url": "javascript:alert(1)",
            "model": "relay-model",
            "api_key": SECRET,
        },
        headers=headers,
    )
    assert bad.status_code == 400
    assert SECRET not in bad.get_data(as_text=True)

    client.put(
        "/api/settings/llm",
        json={
            "provider": "openai",
            "base_url": "https://relay.example/v1",
            "model": "relay-model",
            "api_key": SECRET,
        },
        headers=headers,
    )
    reset = client.post("/api/settings/llm/reset", headers=headers)
    assert reset.status_code == 200
    assert reset.get_json()["source"] == "env"
    assert reset.get_json()["model"] == "env-model"
    assert SECRET not in reset.get_data(as_text=True)
    assert not __import__("pathlib").Path(app.config["LLM_SETTINGS_PATH"]).exists()


def test_connection_probe_uses_form_and_hides_key(client):
    headers = _login(client)
    with patch("app.routes.settings.probe_llm", return_value="OK") as probe:
        response = client.post(
            "/api/settings/llm/test",
            json={
                "provider": "openai",
                "base_url": "https://relay.example/v1",
                "model": "relay-model",
                "api_key": SECRET,
            },
            headers=headers,
        )
    assert response.status_code == 200
    assert response.get_json()["reply"] == "OK"
    assert SECRET not in response.get_data(as_text=True)
    assert probe.call_args.args[0]["api_key"] == SECRET


def test_settings_require_login(client):
    assert client.get("/api/settings/llm").status_code == 401
