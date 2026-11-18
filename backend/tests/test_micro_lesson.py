"""Weak-topic lessons stay inside DSE notes. No Chroma client, no real LLM."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.pool import StaticPool

from app import create_app, db
from app.config import DevelopmentConfig, config_by_name
from app.models import AttemptDetail, KnowledgePoint, MicroLesson, Question, QuizAttempt, Subject, Topic, User
from app.services.chroma_store import RetrievalResult
from app.services.micro_lesson import LessonService, parse_lesson_payload, pick_weakest

GOOD_LESSON = json.dumps(
    {
        "objective": "學懂判別式點樣判斷實根數目。",
        "explanation": "資料 1 指出判別式 Δ = b² − 4ac。正數有兩個不等實根。",
        "example": {
            "prompt": "已知 x² − 5x + 6 = 0，試判斷實根數目。",
            "steps": ["先寫出 a、b、c。", "再計算 b² − 4ac，唔好急住寫根。"],
            "withheld": False,
        },
        "checks": [
            {
                "stem": "若判別式大於 0，實根數目是？",
                "options": {"A": "0", "B": "1", "C": "2", "D": "無限"},
                "correct_answer": "C",
                "explanation": "資料 1 寫明正數有兩個不等實根。",
            }
        ],
    },
    ensure_ascii=False,
)


class _SqliteTestConfig(DevelopmentConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }


class FakeStore:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def query(self, query_text, top_k=5, subject_filter=None, content_type_filter=None, similarity_threshold=0.65):
        self.calls.append(
            {
                "query_text": query_text,
                "subject_filter": subject_filter,
                "content_type_filter": content_type_filter,
            }
        )
        return list(self.hits)

    def query_user_docs(self, *args, **kwargs):
        raise AssertionError("a lesson must not search private notes")


class FakeLLM:
    def __init__(self, text):
        self.text = text
        self.available = True
        self.calls = 0

    def complete(self, user, system=None, max_tokens=2048, temperature=0.7, json_mode=False, history=None):
        self.calls += 1
        self.last_user = user
        return self.text


def _hit(text="判別式 Δ = b² − 4ac。正數有兩個不等實根。", **metadata):
    return RetrievalResult(
        id="dse-quad-1",
        text=text,
        metadata={"subject": "math", "content_type": "math_topic", **metadata},
        distance=0.2,
        relevance_score=0.8,
    )


def test_pick_weakest_prefers_lower_mastery():
    weak = SimpleNamespace(knowledge_point_id=2, mastery_percent=20, total_attempts=1)
    strong = SimpleNamespace(knowledge_point_id=9, mastery_percent=80, total_attempts=5)
    assert pick_weakest([strong, weak]).knowledge_point_id == 2
    assert pick_weakest([]) is None


def test_parse_rejects_latex_and_leaked_math_answer():
    leaked = json.dumps(
        {
            "objective": "學判別式。",
            "explanation": "資料 1。",
            "example": {"prompt": "題目", "steps": ["答案：x = 2", "再驗算。"]},
            "checks": [
                {
                    "stem": "問",
                    "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                    "correct_answer": "A",
                    "explanation": "見資料。",
                }
            ],
        },
        ensure_ascii=False,
    )
    with pytest.raises(ValueError):
        parse_lesson_payload(leaked, math=True)
    with pytest.raises(ValueError):
        parse_lesson_payload(GOOD_LESSON.replace("正數", "$x$"), math=False)
    assert parse_lesson_payload('{"insufficient": true}', math=True) is None


@pytest.fixture
def app():
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
def world(app):
    with app.app_context():
        subject = Subject(code="MATH", name_en="Mathematics", name_zh="數學")
        topic = Topic(subject=subject, name_en="Algebra", name_zh="代數", sort_order=1)
        weak = KnowledgePoint(
            topic=topic,
            code="MATH-QUAD-01",
            name_en="Discriminant",
            name_zh="判別式",
            dse_level_hint="level_4",
        )
        strong = KnowledgePoint(
            topic=topic,
            code="MATH-QUAD-02",
            name_en="Formula",
            name_zh="二次公式",
            dse_level_hint="level_4",
        )
        user_a = User(email="a@example.com", username="student_a", display_name="A")
        user_a.set_password("password-a")
        user_b = User(email="b@example.com", username="student_b", display_name="B")
        user_b.set_password("password-b")
        user_c = User(email="c@example.com", username="student_c", display_name="C")
        user_c.set_password("password-c")
        db.session.add_all([subject, topic, weak, strong, user_a, user_b, user_c])
        db.session.flush()

        def _attempt(user, kp, correct):
            question = Question(
                knowledge_point=kp,
                question_type="mc",
                difficulty="level_4",
                stem="舊題",
                options_json=json.dumps({"A": "1", "B": "2", "C": "3", "D": "4"}),
                correct_answer="A",
                source="ai_generated",
            )
            attempt = QuizAttempt(
                user=user,
                subject_id=subject.id,
                topic_id=topic.id,
                title="舊測驗",
                difficulty="level_4",
                total_questions=1,
                correct_count=1 if correct else 0,
                score_percent=100 if correct else 0,
                status="completed",
                completed_at=datetime.now(timezone.utc),
            )
            detail = AttemptDetail(
                attempt=attempt,
                question=question,
                knowledge_point=kp,
                user_answer="A" if correct else "B",
                is_correct=correct,
                time_spent=20,
            )
            db.session.add_all([question, attempt, detail])

        _attempt(user_a, weak, False)
        _attempt(user_a, strong, True)
        db.session.commit()
        return {
            "a": {"email": user_a.email, "password": "password-a", "id": user_a.id},
            "b": {"email": user_b.email, "password": "password-b", "id": user_b.id},
            "c": {"email": user_c.email, "password": "password-c", "id": user_c.id},
            "weak_id": weak.id,
            "strong_id": strong.id,
        }


def _login(client, email, password):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.get_data(as_text=True)
    csrf = client.get_cookie("csrf_access_token")
    assert csrf is not None
    return {"X-CSRF-TOKEN": csrf.value}


def _patched(hits, text=GOOD_LESSON):
    store = FakeStore(hits)
    llm = FakeLLM(text)
    service = LessonService(store, llm)
    return store, llm, patch("app.routes.lessons._service", return_value=service)


def test_lesson_uses_weakest_point_and_hides_answers(client, world, app):
    headers = _login(client, world["a"]["email"], world["a"]["password"])
    store, llm, patched = _patched([_hit()])
    with patched:
        response = client.post(
            "/api/lessons",
            json={"topic": "任意課題", "user_id": world["b"]["id"]},
            headers=headers,
        )
    assert response.status_code == 201, response.get_data(as_text=True)
    body = response.get_json()
    assert body["status"] == "ready"
    assert body["knowledge_point"]["id"] == world["weak_id"]
    assert body["knowledge_point"]["name_zh"] == "判別式"
    assert body["example"]["withheld"] is True
    assert body["questions"][0]["options"]["C"] == "2"
    assert "correct_answer" not in json.dumps(body, ensure_ascii=False)
    assert body["sources"][0]["preview"].startswith("判別式")
    assert store.calls[0]["subject_filter"] == "math"
    assert llm.calls == 1

    with app.app_context():
        lesson = MicroLesson.query.one()
        assert lesson.user_id == world["a"]["id"]
        question = Question.query.filter_by(source="lesson_check").one()
        assert question.knowledge_point_id == world["weak_id"]
        assert question.correct_answer == "C"

    other = _login(client, world["b"]["email"], world["b"]["password"])
    hidden = client.get(f"/api/lessons/{body['id']}", headers=other)
    assert hidden.status_code == 404

    owner = _login(client, world["a"]["email"], world["a"]["password"])
    submit = client.post(
        "/api/quiz/submit",
        json={
            "attempt_id": body["attempt_id"],
            "answers": {str(body["questions"][0]["id"]): "C"},
            "time_per_question": {str(body["questions"][0]["id"]): 12},
        },
        headers=owner,
    )
    assert submit.status_code == 200
    assert submit.get_json()["score_percent"] == 100
    with app.app_context():
        detail = AttemptDetail.query.filter_by(attempt_id=body["attempt_id"]).one()
        assert detail.knowledge_point_id == world["weak_id"]
        assert detail.is_correct is True


def test_explicit_point_is_used_and_private_hits_are_dropped(client, world, app):
    headers = _login(client, world["a"]["email"], world["a"]["password"])
    store, llm, patched = _patched([_hit(origin="user_upload", user_id="8")])
    with patched:
        denied = client.post(
            "/api/lessons",
            json={"knowledge_point_id": world["strong_id"], "topic": "自由課題"},
            headers=headers,
        )
    assert denied.status_code == 200
    assert denied.get_json()["status"] == "insufficient"
    assert denied.get_json()["knowledge_point"]["id"] == world["strong_id"]
    assert llm.calls == 0
    with app.app_context():
        assert MicroLesson.query.count() == 0

    store.hits = [_hit()]
    with patched:
        created = client.post(
            "/api/lessons",
            json={"knowledge_point_id": world["strong_id"], "user_id": world["b"]["id"]},
            headers=headers,
        )
    assert created.status_code == 201
    assert created.get_json()["knowledge_point"]["name_zh"] == "二次公式"
    with app.app_context():
        assert MicroLesson.query.one().user_id == world["a"]["id"]


def test_missing_notes_and_bad_model_do_not_invent_a_lesson(client, world, app):
    headers = _login(client, world["a"]["email"], world["a"]["password"])
    store, llm, patched = _patched([])
    with patched:
        empty = client.post("/api/lessons", json={}, headers=headers)
    assert empty.status_code == 200
    assert empty.get_json()["status"] == "insufficient"
    assert llm.calls == 0

    store.hits = [_hit()]
    llm.text = '{"insufficient": true}'
    with patched:
        honest = client.post("/api/lessons", json={"fresh": True}, headers=headers)
    assert honest.get_json()["status"] == "insufficient"
    assert llm.calls == 1

    llm.text = GOOD_LESSON.replace("正數", "$\\\\frac{1}{2}$")
    with patched:
        bad = client.post("/api/lessons", json={"fresh": True}, headers=headers)
    assert bad.status_code == 502
    with app.app_context():
        assert MicroLesson.query.count() == 0


def test_in_progress_lesson_is_reused_without_another_model_call(client, world):
    headers = _login(client, world["a"]["email"], world["a"]["password"])
    _store, llm, patched = _patched([_hit()])
    with patched:
        first = client.post("/api/lessons", json={}, headers=headers)
        second = client.post("/api/lessons", json={"topic": "再生成"}, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.get_json()["id"] == first.get_json()["id"]
    assert llm.calls == 1


def test_no_history_does_not_open_a_free_topic(client, world):
    headers = _login(client, world["c"]["email"], world["c"]["password"])
    with patch("app.routes.lessons._service", side_effect=AssertionError("should not retrieve")):
        response = client.post(
            "/api/lessons",
            json={"topic": "請生成成個課題"},
            headers=headers,
        )
    assert response.status_code == 409
    assert "測驗" in response.get_json()["error"]


def test_lessons_require_login(client):
    assert client.get("/api/lessons/latest").status_code == 401
