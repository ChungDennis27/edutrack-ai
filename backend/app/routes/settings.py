"""Operator settings for the shared LLM endpoint. Login required."""
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required

from app.services.llm_settings import (
    SettingsError,
    effective_llm_config,
    probe_llm,
    public_view,
    reset_settings,
    save_settings,
    settings_path,
    validate_settings,
)

settings_bp = Blueprint("settings", __name__)


def _payload() -> dict:
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        raise SettingsError("設定格式不正確")
    return data


@settings_bp.route("/llm", methods=["GET"])
@jwt_required()
def get_llm_settings():
    return jsonify(public_view(effective_llm_config(current_app.config)))


@settings_bp.route("/llm", methods=["PUT"])
@jwt_required()
def update_llm_settings():
    try:
        current = effective_llm_config(current_app.config)
        settings = validate_settings(_payload(), fallback_key=current.get("api_key") or "")
        path = settings_path(current_app.config)
        if path is None:
            raise SettingsError("未設定 LLM_SETTINGS_PATH", 500)
        save_settings(path, settings)
    except SettingsError as exc:
        return jsonify({"error": exc.message}), exc.status
    current_app.logger.info("updated llm settings provider=%s model=%s", settings["provider"], settings["model"])
    return jsonify(public_view(settings))


@settings_bp.route("/llm/test", methods=["POST"])
@jwt_required()
def test_llm_settings():
    try:
        current = effective_llm_config(current_app.config)
        settings = validate_settings(_payload(), fallback_key=current.get("api_key") or "")
        reply = probe_llm(settings)
    except SettingsError as exc:
        return jsonify({"error": exc.message}), exc.status
    return jsonify({"ok": True, "reply": reply})


@settings_bp.route("/llm/reset", methods=["POST"])
@jwt_required()
def reset_llm_settings():
    path = settings_path(current_app.config)
    if path is not None:
        reset_settings(path)
    return jsonify(public_view(effective_llm_config(current_app.config)))
