"""Database seed script — creates sample subjects, topics, and knowledge points.

Usage:
    python scripts/seed_db.py
"""
import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from app import create_app, db
from app.models import KnowledgePoint, Subject, Topic


def seed():
    """Insert sample DSE curriculum taxonomy."""
    app = create_app()

    with app.app_context():
        # Check if already seeded
        if Subject.query.first():
            print("Database already has data. Skipping seed.")
            return

        subjects_data = [
            {
                "code": "MATH",
                "name_en": "Mathematics",
                "name_zh": "數學",
                "topics": [
                    {
                        "name_en": "Quadratic Equations",
                        "name_zh": "二次方程",
                        "syllabus_ref": "Compulsory Part 1",
                        "knowledge_points": [
                            {
                                "code": "MATH-QUAD-01",
                                "name_en": "Solving by factorization",
                                "name_zh": "因式分解法",
                                "dse_level": "level_3",
                            },
                            {
                                "code": "MATH-QUAD-02",
                                "name_en": "Quadratic formula",
                                "name_zh": "二次公式",
                                "dse_level": "level_4",
                            },
                            {
                                "code": "MATH-QUAD-03",
                                "name_en": "Discriminant analysis",
                                "name_zh": "判別式分析",
                                "dse_level": "level_4",
                            },
                            {
                                "code": "MATH-QUAD-04",
                                "name_en": "Word problems",
                                "name_zh": "應用題",
                                "dse_level": "level_5",
                            },
                        ],
                    },
                    {
                        "name_en": "Calculus",
                        "name_zh": "微積分",
                        "syllabus_ref": "Compulsory Part 2",
                        "knowledge_points": [
                            {
                                "code": "MATH-CALC-01",
                                "name_en": "Differentiation",
                                "name_zh": "微分",
                                "dse_level": "level_4",
                            },
                            {
                                "code": "MATH-CALC-02",
                                "name_en": "Integration",
                                "name_zh": "積分",
                                "dse_level": "level_5",
                            },
                        ],
                    },
                ],
            },
            {
                "code": "CHI",
                "name_en": "Chinese Language",
                "name_zh": "中國語文",
                "topics": [
                    {
                        "name_en": "Classical Chinese Texts",
                        "name_zh": "文言文",
                        "syllabus_ref": "Paper 1",
                        "knowledge_points": [
                            {
                                "code": "CHI-CLASS-01",
                                "name_en": "論仁",
                                "name_zh": "論仁",
                                "dse_level": "level_4",
                            },
                            {
                                "code": "CHI-CLASS-02",
                                "name_en": "論孝",
                                "name_zh": "論孝",
                                "dse_level": "level_4",
                            },
                            {
                                "code": "CHI-CLASS-03",
                                "name_en": "勸學",
                                "name_zh": "勸學",
                                "dse_level": "level_5",
                            },
                        ],
                    },
                    {
                        "name_en": "Modern Chinese Reading",
                        "name_zh": "現代文閱讀",
                        "syllabus_ref": "Paper 1",
                        "knowledge_points": [
                            {
                                "code": "CHI-MOD-01",
                                "name_en": "Comprehension strategies",
                                "name_zh": "閱讀理解策略",
                                "dse_level": "level_3",
                            },
                        ],
                    },
                ],
            },
            {
                "code": "ENG",
                "name_en": "English Language",
                "name_zh": "英國語文",
                "topics": [
                    {
                        "name_en": "Writing",
                        "name_zh": "寫作",
                        "syllabus_ref": "Paper 2",
                        "knowledge_points": [
                            {
                                "code": "ENG-WRT-01",
                                "name_en": "Argumentative essay",
                                "name_zh": "議論文",
                                "dse_level": "level_4",
                            },
                            {
                                "code": "ENG-WRT-02",
                                "name_en": "Narrative writing",
                                "name_zh": "敘事文",
                                "dse_level": "level_4",
                            },
                        ],
                    },
                    {
                        "name_en": "Reading",
                        "name_zh": "閱讀",
                        "syllabus_ref": "Paper 1",
                        "knowledge_points": [
                            {
                                "code": "ENG-READ-01",
                                "name_en": "Reading comprehension",
                                "name_zh": "閱讀理解",
                                "dse_level": "level_3",
                            },
                        ],
                    },
                ],
            },
        ]

        for subj_data in subjects_data:
            subject = Subject(
                code=subj_data["code"],
                name_en=subj_data["name_en"],
                name_zh=subj_data["name_zh"],
            )
            db.session.add(subject)
            db.session.flush()

            for topic_data in subj_data["topics"]:
                topic = Topic(
                    subject_id=subject.id,
                    name_en=topic_data["name_en"],
                    name_zh=topic_data["name_zh"],
                    syllabus_ref=topic_data.get("syllabus_ref"),
                )
                db.session.add(topic)
                db.session.flush()

                for kp_data in topic_data["knowledge_points"]:
                    kp = KnowledgePoint(
                        topic_id=topic.id,
                        code=kp_data["code"],
                        name_en=kp_data["name_en"],
                        name_zh=kp_data["name_zh"],
                        dse_level_hint=kp_data.get("dse_level"),
                    )
                    db.session.add(kp)

        db.session.commit()
        print(f"Seeded {len(subjects_data)} subjects with topics and knowledge points.")


if __name__ == "__main__":
    seed()
