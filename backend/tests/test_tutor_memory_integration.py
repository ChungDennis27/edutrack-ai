"""Prove L1 history and L2 student context reach /api/chat. No LLM, no Chroma."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.pool import StaticPool

from app import create_app, db
from app.config import DevelopmentConfig, config_by_name
from app.models import (
    AttemptDetail,
    Flashcard,
    KnowledgePoint,
    Question,
    QuizAttempt,
    Subject,
    Topic,
    TopicMastery,
    User,
)

CHAT_BODY = {
    "query": "再講淺啲",
    "subject": "math",
    "history": [
        {"role": "user", "content": "二次方程點解"},
        {"role": "assistant", "content": "先試判別式"},
    ],
}
STREAM_CHUNKS = ("再講：第一步", "再講：第二步")


class _SqliteTestConfig(DevelopmentConfig):
    """Applied before init_app. Flask-SQLAlchemy 3 builds the engine there,
    and the default postgres URI needs psycopg2, which is not installed.
    """

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }


class RecordingEngine:
    def __init__(self):
        self.chat_calls = []
        self.stream_calls = []

    def chat(self, query, subject=None, history=None, student_context=None):
        self.chat_calls.append(
            {
                "query": query,
                "subject": subject,
                "history": history,
                "student_context": student_context,
            }
        )
        return {"answer": "ok", "sources": []}

    def chat_stream(self, query, subject=None, history=None, student_context=None):
        self.stream_calls.append(
            {
                "query": query,
                "subject": subject,
                "history": history,
                "student_context": student_context,
            }
        )
        yield from STREAM_CHUNKS


def _engine_options():
    return {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }


@pytest.fixture
def app():
    config_by_name["testing"] = _SqliteTestConfig
    try:
        application = create_app("testing")
    finally:
        config_by_name.pop("testing", None)

    application.config["TESTING"] = True
    application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    application.config["SQLALCHEMY_ENGINE_OPTIONS"] = _engine_options()

    with application.app_context():
        # Drop the engine created at init_app so create_all cannot keep a
        # postgres (or stale) pool, then bind sqlite:// explicitly.
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
def engine():
    return RecordingEngine()


@pytest.fixture
def patched_engine(engine):
    from unittest.mock import patch

    with patch("app.routes.ai_tutor._get_engine", return_value=engine):
        yield engine


@pytest.fixture
def users(app):
    """User A has the quadratic weak point, a wrong attempt, and a due card.
    User B has an unrelated weak point. User C has no learning records.
    """
    with app.app_context():
        subject = Subject(code="MATH", name_en="Mathematics", name_zh="數學")
        topic = Topic(subject=subject, name_en="Algebra", name_zh="代數", sort_order=1)
        kp = KnowledgePoint(
            topic=topic,
            code="MATH-QUAD",
            name_en="Quadratic equations",
            name_zh="二次方程",
        )
        topic_b = Topic(subject=subject, name_en="Other", name_zh="其他", sort_order=2)
        kp_b = KnowledgePoint(
            topic=topic_b,
            code="UNRELATED",
            name_en="Unrelated topic",
            name_zh="完全唔相關的課題",
        )
        user_a = User(email="a@example.com", username="student_a", display_name="A")
        user_a.set_password("password-a")
        user_b = User(email="b@example.com", username="student_b", display_name="B")
        user_b.set_password("password-b")
        user_c = User(email="c@example.com", username="student_c", display_name="C")
        user_c.set_password("password-c")
        db.session.add_all(
            [subject, topic, kp, topic_b, kp_b, user_a, user_b, user_c]
        )
        db.session.flush()

        question = Question(
            knowledge_point=kp,
            question_type="short",
            difficulty="level_4",
            stem="解二次方程 x^2-5x+6=0",
            correct_answer="x=2 或 x=3",
        )
        attempt = QuizAttempt(
            user=user_a,
            subject_id=subject.id,
            topic_id=topic.id,
            title="二次方程小測",
            difficulty="level_4",
            total_questions=1,
            correct_count=0,
            score_percent=0,
            total_time_spent=40,
            status="completed",
            completed_at=datetime.now(timezone.utc),
        )
        detail = AttemptDetail(
            attempt=attempt,
            question=question,
            knowledge_point=kp,
            user_answer="x=1",
            is_correct=False,
            time_spent=20,
        )
        db.session.add_all(
            [
                question,
                attempt,
                detail,
                TopicMastery(
                    user=user_a,
                    knowledge_point=kp,
                    mastery_percent=32,
                    total_attempts=4,
                    correct_count=0,
                    is_weak=True,
                ),
                TopicMastery(
                    user=user_b,
                    knowledge_point=kp_b,
                    mastery_percent=10,
                    total_attempts=3,
                    correct_count=0,
                    is_weak=True,
                ),
                Flashcard(
                    user=user_a,
                    knowledge_point_id=kp.id,
                    front="判別式代表什麼",
                    back="b^2-4ac",
                    next_review_date=datetime.now(timezone.utc) - timedelta(days=1),
                    is_active=True,
                ),
            ]
        )
        db.session.commit()
        return {
            "a": {"email": user_a.email, "password": "password-a", "id": user_a.id},
            "b": {"email": user_b.email, "password": "password-b", "id": user_b.id},
            "c": {"email": user_c.email, "password": "password-c", "id": user_c.id},
        }


def _login(client, email, password):
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    csrf = client.get_cookie("csrf_access_token")
    assert csrf is not None, "login did not set csrf_access_token"
    return {"X-CSRF-TOKEN": csrf.value}


def _assert_history(history):
    assert isinstance(history, list)
    contents = [
        item.get("content")
        for item in history
        if isinstance(item, dict) and isinstance(item.get("content"), str)
    ]
    assert "二次方程點解" in contents, history


def _assert_student_context(student_context):
    assert isinstance(student_context, str) and student_context, student_context
    assert "二次方程" in student_context
    assert "32" in student_context
    assert "x=1" in student_context
    assert "判別式代表什麼" in student_context
    assert "完全唔相關的課題" not in student_context


def _sse_data_lines(response):
    text = response.get_data(as_text=True)
    return [
        line[len("data:") :].strip()
        for line in text.splitlines()
        if line.startswith("data:")
    ]


def test_query_and_stream_receive_history_and_student_context(
    client, users, patched_engine
):
    headers = _login(client, users["a"]["email"], users["a"]["password"])

    query_response = client.post("/api/chat/query", json=CHAT_BODY, headers=headers)
    assert query_response.status_code == 200
    assert query_response.get_json() == {"answer": "ok", "sources": []}
    assert len(patched_engine.chat_calls) == 1
    chat_call = patched_engine.chat_calls[0]
    assert chat_call["query"] == "再講淺啲"
    assert chat_call["subject"] == "math"
    _assert_history(chat_call["history"])
    _assert_student_context(chat_call["student_context"])

    stream_response = client.post("/api/chat/stream", json=CHAT_BODY, headers=headers)
    assert stream_response.status_code == 200
    assert stream_response.mimetype == "text/event-stream"
    data_lines = _sse_data_lines(stream_response)
    payloads = [json.loads(line) for line in data_lines if line != "[DONE]"]
    assert [item["text"] for item in payloads] == list(STREAM_CHUNKS)
    assert data_lines[-1] == "[DONE]"

    assert len(patched_engine.stream_calls) == 1
    stream_call = patched_engine.stream_calls[0]
    assert stream_call["history"] == chat_call["history"]
    assert stream_call["student_context"] == chat_call["student_context"]
    assert stream_call["student_context"] != ""


def test_query_without_jwt_returns_401(client, patched_engine):
    response = client.post("/api/chat/query", json=CHAT_BODY)
    assert response.status_code == 401
    assert patched_engine.chat_calls == []
    assert patched_engine.stream_calls == []


def test_user_with_no_records_gets_empty_context_and_200(
    client, users, patched_engine
):
    headers = _login(client, users["c"]["email"], users["c"]["password"])
    response = client.post(
        "/api/chat/query",
        json={"query": "你好", "subject": "math"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json()["answer"] == "ok"
    assert len(patched_engine.chat_calls) == 1
    assert patched_engine.chat_calls[0]["student_context"] == ""
