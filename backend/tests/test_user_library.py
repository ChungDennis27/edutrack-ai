"""Personal library quota, isolation, and upload routes. No Chroma, no LLM."""
import io
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.pool import StaticPool

from app import create_app, db
from app.config import DevelopmentConfig, config_by_name
from app.models import User, UserDocument
from app.services.retrieval_scope import merge_by_relevance, normalize_scope, visible_to
from app.services.user_library import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    LibraryError,
    check_quota,
    safe_display_name,
)


class _SqliteTestConfig(DevelopmentConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }


class FakeStore:
    def __init__(self):
        self.chunks = []
        self.deleted = []

    def upsert_user_chunks(self, chunks, user_id):
        owner = str(user_id)
        for chunk in chunks:
            assert chunk.metadata.get("origin") == "user_upload"
            assert str(chunk.metadata.get("user_id")) == owner
            assert chunk.metadata.get("document_id")
        self.chunks.extend(chunks)
        return len(chunks)

    def delete_user_document(self, user_id, document_id):
        self.deleted.append((str(user_id), str(document_id)))
        self.chunks = [
            chunk
            for chunk in self.chunks
            if not (
                str(chunk.metadata.get("user_id")) == str(user_id)
                and str(chunk.metadata.get("document_id")) == str(document_id)
            )
        ]


def test_quota_limits():
    check_quota(0, 0, 100)
    with pytest.raises(LibraryError) as empty:
        check_quota(0, 0, 0)
    assert empty.value.status == 400
    with pytest.raises(LibraryError) as huge:
        check_quota(0, 0, MAX_FILE_BYTES + 1)
    assert huge.value.status == 413
    with pytest.raises(LibraryError) as files:
        check_quota(MAX_FILES, 0, 10)
    assert files.value.status == 409
    with pytest.raises(LibraryError) as total:
        check_quota(1, MAX_TOTAL_BYTES - 5, 10)
    assert total.value.status == 409


def test_safe_display_name_rejects_other_types():
    name, ext = safe_display_name(r"..\secret\notes.MD")
    assert name == "notes.md"
    assert ext == ".md"
    with pytest.raises(LibraryError):
        safe_display_name("malware.pdf.exe")


def test_visible_to_never_crosses_users():
    mine = {"origin": "user_upload", "user_id": "7"}
    theirs = {"origin": "user_upload", "user_id": "8"}
    dse = {"subject": "math", "content_type": "math_topic"}

    assert visible_to(dse, "dse", 7) is True
    assert visible_to(mine, "dse", 7) is False
    assert visible_to(mine, "my_docs", 7) is True
    assert visible_to(theirs, "my_docs", 7) is False
    assert visible_to(theirs, "all", 7) is False
    assert visible_to(mine, "all", None) is False
    assert visible_to(dse, "all", 7) is True
    assert normalize_scope("nope") == "dse"


def test_merge_prefers_higher_relevance_and_dedupes():
    low = SimpleNamespace(id="a", relevance_score=0.2)
    high = SimpleNamespace(id="b", relevance_score=0.9)
    dup = SimpleNamespace(id="a", relevance_score=0.8)
    merged = merge_by_relevance([[low], [high, dup]], top_k=2)
    assert [item.id for item in merged] == ["b", "a"]


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
    application.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    with application.app_context():
        db.engine.dispose()
        from sqlalchemy import create_engine

        db._app_engines[application][None] = create_engine(
            application.config["SQLALCHEMY_DATABASE_URI"],
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def store():
    return FakeStore()


@pytest.fixture
def patched_store(store):
    with patch("app.routes.uploads._get_store", return_value=store):
        yield store


@pytest.fixture
def users(app):
    with app.app_context():
        user_a = User(email="a@example.com", username="student_a", display_name="A")
        user_a.set_password("password-a")
        user_b = User(email="b@example.com", username="student_b", display_name="B")
        user_b.set_password("password-b")
        db.session.add_all([user_a, user_b])
        db.session.commit()
        return {
            "a": {"email": user_a.email, "password": "password-a", "id": user_a.id},
            "b": {"email": user_b.email, "password": "password-b", "id": user_b.id},
        }


def _login(client, email, password):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.get_data(as_text=True)
    csrf = client.get_cookie("csrf_access_token")
    assert csrf is not None
    return {"X-CSRF-TOKEN": csrf.value}


def _upload(client, headers, filename, content, subject="math"):
    return client.post(
        "/api/uploads",
        data={
            "subject": subject,
            "file": (io.BytesIO(content), filename),
        },
        headers=headers,
    )


def test_upload_is_private_and_tagged_with_user_id(client, users, patched_store, app):
    headers = _login(client, users["a"]["email"], users["a"]["password"])
    response = _upload(
        client,
        headers,
        "二次方程筆記.txt",
        "判別式 Δ = b² − 4ac，用來判斷二次方程有幾多個實根。".encode("utf-8"),
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    body = response.get_json()["document"]
    assert body["status"] == "ready"
    assert body["chunk_count"] >= 1
    assert body["filename"] == "二次方程筆記.txt"
    assert patched_store.chunks
    assert all(chunk.metadata["user_id"] == str(users["a"]["id"]) for chunk in patched_store.chunks)
    assert "user_upload" == patched_store.chunks[0].metadata["origin"]

    with app.app_context():
        stored = UserDocument.query.filter_by(user_id=users["a"]["id"]).one()
        folder = app.config["UPLOAD_DIR"]
        from pathlib import Path

        saved = list(Path(folder, str(users["a"]["id"])).iterdir())
        assert len(saved) == 1
        assert saved[0].name == stored.stored_name
        assert saved[0].name != stored.original_filename

    other = _login(client, users["b"]["email"], users["b"]["password"])
    listed = client.get("/api/uploads")
    assert listed.status_code == 200
    assert listed.get_json()["documents"] == []

    denied = client.delete(f"/api/uploads/{body['id']}", headers=other)
    assert denied.status_code == 404
    assert patched_store.deleted == []

    owner = _login(client, users["a"]["email"], users["a"]["password"])
    deleted = client.delete(f"/api/uploads/{body['id']}", headers=owner)
    assert deleted.status_code == 200
    assert patched_store.deleted == [(str(users["a"]["id"]), str(body["id"]))]
    assert patched_store.chunks == []
    with app.app_context():
        assert UserDocument.query.count() == 0


def test_rejects_bad_type_empty_text_and_file_cap(client, users, patched_store, app):
    headers = _login(client, users["a"]["email"], users["a"]["password"])

    bad = _upload(client, headers, "notes.exe", b"not allowed")
    assert bad.status_code == 400
    assert patched_store.chunks == []

    fake_pdf = _upload(client, headers, "scan.pdf", b"this is not a pdf")
    assert fake_pdf.status_code == 400

    short = _upload(client, headers, "tiny.txt", "太短".encode("utf-8"))
    assert short.status_code == 201
    assert short.get_json()["document"]["status"] == "empty"
    assert patched_store.chunks == []

    with app.app_context():
        now = datetime.now(timezone.utc)
        for i in range(MAX_FILES - 1):
            db.session.add(
                UserDocument(
                    user_id=users["a"]["id"],
                    original_filename=f"extra-{i}.txt",
                    stored_name=f"{i}.txt",
                    subject="general",
                    size_bytes=10,
                    status="ready",
                    chunk_count=0,
                    created_at=now,
                )
            )
        db.session.commit()

    capped = _upload(
        client,
        headers,
        "one-more.txt",
        "這是一段足夠長的筆記，用來測試檔案數量上限。".encode("utf-8"),
    )
    assert capped.status_code == 409


def test_uploads_require_login(client):
    response = client.get("/api/uploads")
    assert response.status_code == 401
