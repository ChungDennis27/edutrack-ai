"""Generate synthetic quiz attempt data for the weakness-analysis dashboard.

Creates demo students with realistic per-knowledge-point mastery profiles and
10 quizzes each, spread across the last 8 weeks so the trend chart is populated.

Usage:
    python scripts/seed_attempts.py                 # 20 students x 10 quizzes
    python scripts/seed_attempts.py --students 10 --quizzes 6
    python scripts/seed_attempts.py --reset         # remove demo data first
"""
import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import create_app, db  # noqa: E402
from app.models import (  # noqa: E402
    AttemptDetail,
    KnowledgePoint,
    Question,
    QuizAttempt,
    Subject,
    Topic,
    User,
)
from app.services.analytics import AnalyticsService  # noqa: E402

DEMO_DOMAIN = "demo.local"
DEMO_PASSWORD = "demo12345"
DIFFICULTIES = ["level_3", "level_4", "level_5"]
SLOW_THRESHOLD_SEC = 120


def clamp(value: float, low: float = 0.05, high: float = 0.98) -> float:
    return max(low, min(high, value))


def reset_demo_data() -> None:
    users = User.query.filter(User.email.like(f"%@{DEMO_DOMAIN}")).all()
    for user in users:
        db.session.delete(user)
    Question.query.filter_by(source="synthetic").delete(synchronize_session=False)
    db.session.commit()
    print(f"Removed {len(users)} demo students and their synthetic questions.")


def build_question(kp: KnowledgePoint, index: int) -> Question:
    return Question(
        knowledge_point_id=kp.id,
        question_type="mc",
        difficulty=random.choice(DIFFICULTIES),
        stem=f"【{kp.name_zh}】示範題目 {index}：以下哪一項描述正確？",
        options_json='{"A": "選項 A", "B": "選項 B", "C": "選項 C", "D": "選項 D"}',
        correct_answer=random.choice(["A", "B", "C", "D"]),
        explanation=f"考核知識點：{kp.name_zh}（{kp.code}）。此為合成示範資料。",
        source="synthetic",
    )


def simulate_quiz(
    user: User, subject: Subject, topic: Topic, kps: list[KnowledgePoint],
    mastery: dict[int, float], completed_at: datetime,
) -> QuizAttempt:
    n = 5
    attempt = QuizAttempt(
        user_id=user.id,
        subject_id=subject.id,
        topic_id=topic.id,
        title=f"{subject.name_zh} · {topic.name_zh} 示範測驗",
        difficulty=random.choice(DIFFICULTIES),
        total_questions=n,
        status="completed",
        started_at=completed_at - timedelta(minutes=random.randint(5, 25)),
        completed_at=completed_at,
    )
    db.session.add(attempt)
    db.session.flush()

    correct_count = 0
    total_time = 0

    for i in range(n):
        kp = kps[i % len(kps)]
        question = build_question(kp, i + 1)
        db.session.add(question)
        db.session.flush()

        p_correct = mastery.get(kp.id, 0.6)
        is_correct = random.random() < p_correct

        base = 35 + (1 - p_correct) * 70
        time_spent = max(5, int(random.gauss(base, 25)))
        is_slow = is_correct and time_spent >= SLOW_THRESHOLD_SEC

        if is_correct:
            correct_count += 1
        total_time += time_spent

        db.session.add(
            AttemptDetail(
                attempt_id=attempt.id,
                question_id=question.id,
                knowledge_point_id=kp.id,
                user_answer="A" if is_correct else random.choice(["B", "C", "D"]),
                is_correct=is_correct,
                time_spent=time_spent,
                is_slow_but_correct=is_slow,
            )
        )

    attempt.correct_count = correct_count
    attempt.score_percent = round(correct_count / n * 100, 1)
    attempt.total_time_spent = total_time
    return attempt


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic attempt data")
    parser.add_argument("--students", type=int, default=20)
    parser.add_argument("--quizzes", type=int, default=10)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    now = datetime.now(timezone.utc)

    app = create_app()
    with app.app_context():
        if args.reset:
            reset_demo_data()

        subjects = Subject.query.all()
        if not subjects:
            print("No subjects found. Run scripts/seed_db.py first.")
            return

        created_attempts = 0
        created_students = 0

        for s in range(1, args.students + 1):
            email = f"demo{s}@{DEMO_DOMAIN}"
            if User.query.filter_by(email=email).first():
                continue

            user = User(
                email=email,
                username=f"demo_student_{s}",
                display_name=f"示範學生 {s}",
                form_level=random.choice([4, 5, 6]),
            )
            user.set_password(DEMO_PASSWORD)
            db.session.add(user)
            db.session.flush()
            created_students += 1

            # Per-student mastery profile across every knowledge point.
            overall = random.uniform(0.4, 0.9)
            mastery: dict[int, float] = {}
            for kp in KnowledgePoint.query.all():
                mastery[kp.id] = clamp(overall + random.uniform(-0.3, 0.3))

            for _ in range(args.quizzes):
                subject = random.choice(subjects)
                topics = Topic.query.filter_by(subject_id=subject.id).all()
                if not topics:
                    continue
                topic = random.choice(topics)
                kps = KnowledgePoint.query.filter_by(topic_id=topic.id).all()
                if not kps:
                    continue

                completed_at = now - timedelta(
                    days=random.uniform(0, 55), hours=random.uniform(0, 23)
                )
                simulate_quiz(user, subject, topic, kps, mastery, completed_at)
                created_attempts += 1

            db.session.commit()
            AnalyticsService.refresh_mastery_cache(user.id)

        print(
            f"Seeded {created_students} students, {created_attempts} quizzes "
            f"({created_attempts * 5} attempt details)."
        )
        print(f"Demo login: demo1@{DEMO_DOMAIN} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
