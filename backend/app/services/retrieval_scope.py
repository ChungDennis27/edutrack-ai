"""Retrieval scope for the shared DSE index vs a student's private notes.

Default remains DSE-only. Personal chunks always carry ``user_id`` and are
never returned to another student, even when scope is ``all``.
"""
from __future__ import annotations

from typing import Any

PERSONAL_ORIGIN = "user_upload"
SCOPES = ("dse", "my_docs", "all")

SCOPE_NOTES = {
    "dse": "今次只搜尋 DSE 課程資料，未包括學生私人筆記。",
    "my_docs": "今次只搜尋這位學生自己上傳的筆記。唔好引用其他學生或未提供的資料。",
    "all": "今次搜尋 DSE 課程資料，以及這位學生自己上傳的筆記。",
}


def normalize_scope(scope: str | None) -> str:
    if isinstance(scope, str) and scope in SCOPES:
        return scope
    return "dse"


def scope_note(scope: str | None) -> str:
    return SCOPE_NOTES[normalize_scope(scope)]


def is_personal(metadata: dict[str, Any] | None) -> bool:
    meta = metadata or {}
    return meta.get("origin") == PERSONAL_ORIGIN or bool(meta.get("user_id"))


def owner_id(metadata: dict[str, Any] | None) -> str:
    return str((metadata or {}).get("user_id") or "")


def visible_to(metadata: dict[str, Any] | None, scope: str | None, user_id: str | int | None) -> bool:
    """True only if this chunk may be shown for the given scope and student."""
    personal = is_personal(metadata)
    owner = owner_id(metadata)
    me = "" if user_id is None else str(user_id)
    chosen = normalize_scope(scope)

    if chosen == "dse":
        return not personal
    if chosen == "my_docs":
        return personal and me != "" and owner == me
    if not personal:
        return True
    return me != "" and owner == me


def merge_by_relevance(groups: list[list], top_k: int) -> list:
    """Dedupe by id and keep the highest-relevance items."""
    ranked = sorted(
        (item for group in groups for item in group),
        key=lambda item: getattr(item, "relevance_score", 0.0),
        reverse=True,
    )
    merged = []
    seen: set[str] = set()
    for item in ranked:
        item_id = str(getattr(item, "id", ""))
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        merged.append(item)
        if len(merged) >= top_k:
            break
    return merged
