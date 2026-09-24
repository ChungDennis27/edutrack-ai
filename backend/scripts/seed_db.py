"""Database seed script — subjects, topics and knowledge points (upsert).

Idempotent: re-running inserts only what is missing, so the taxonomy can be
expanded over time without wiping existing data.

Usage:
    python scripts/seed_db.py
"""
import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from app import create_app, db  # noqa: E402
from app.models import KnowledgePoint, Subject, Topic  # noqa: E402

SUBJECTS = [
    {
        "code": "MATH",
        "name_en": "Mathematics",
        "name_zh": "數學",
        "topics": [
            {
                "name_en": "Quadratic Equations",
                "name_zh": "二次方程",
                "syllabus_ref": "Compulsory Part",
                "knowledge_points": [
                    ("MATH-QUAD-01", "Solving by factorization", "因式分解法", "level_3"),
                    ("MATH-QUAD-02", "Quadratic formula", "二次公式", "level_4"),
                    ("MATH-QUAD-03", "Discriminant analysis", "判別式分析", "level_4"),
                    ("MATH-QUAD-04", "Word problems", "應用題", "level_5"),
                ],
            },
            {
                "name_en": "Calculus",
                "name_zh": "微積分",
                "syllabus_ref": "Compulsory Part",
                "knowledge_points": [
                    ("MATH-CALC-01", "Differentiation", "微分", "level_4"),
                    ("MATH-CALC-02", "Integration", "積分", "level_5"),
                ],
            },
            {
                "name_en": "Trigonometry",
                "name_zh": "三角學",
                "syllabus_ref": "Compulsory Part",
                "knowledge_points": [
                    ("MATH-TRIG-01", "Trigonometric identities", "三角恆等式", "level_4"),
                    ("MATH-TRIG-02", "Sine and cosine formulae", "正弦與餘弦公式", "level_4"),
                    ("MATH-TRIG-03", "Trigonometric equations", "三角方程", "level_5"),
                ],
            },
            {
                "name_en": "Probability and Statistics",
                "name_zh": "概率與統計",
                "syllabus_ref": "Compulsory Part",
                "knowledge_points": [
                    ("MATH-STAT-01", "Permutations and combinations", "排列與組合", "level_4"),
                    ("MATH-STAT-02", "Probability", "概率", "level_4"),
                    ("MATH-STAT-03", "Measures of statistics", "統計量", "level_3"),
                ],
            },
            {
                "name_en": "Sequences",
                "name_zh": "數列",
                "syllabus_ref": "Compulsory Part",
                "knowledge_points": [
                    ("MATH-SEQ-01", "Arithmetic sequences", "等差數列", "level_3"),
                    ("MATH-SEQ-02", "Geometric sequences", "等比數列", "level_4"),
                ],
            },
            {
                "name_en": "Coordinate Geometry",
                "name_zh": "坐標幾何",
                "syllabus_ref": "Compulsory Part",
                "knowledge_points": [
                    ("MATH-GEO-01", "Equations of straight lines", "直線方程", "level_3"),
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
                "name_zh": "文言文（指定篇章）",
                "syllabus_ref": "Paper 1",
                "knowledge_points": [
                    ("CHI-CLASS-01", "論仁、論孝、論君子", "論仁、論孝、論君子", "level_4"),
                    ("CHI-CLASS-02", "魚我所欲也", "魚我所欲也", "level_4"),
                    ("CHI-CLASS-03", "逍遙遊", "逍遙遊", "level_5"),
                    ("CHI-CLASS-04", "勸學", "勸學", "level_5"),
                    ("CHI-CLASS-05", "廉頗藺相如列傳", "廉頗藺相如列傳", "level_4"),
                    ("CHI-CLASS-06", "出師表", "出師表", "level_4"),
                    ("CHI-CLASS-07", "師說", "師說", "level_4"),
                    ("CHI-CLASS-08", "始得西山宴遊記", "始得西山宴遊記", "level_5"),
                    ("CHI-CLASS-09", "岳陽樓記", "岳陽樓記", "level_4"),
                    ("CHI-CLASS-10", "六國論", "六國論", "level_5"),
                    ("CHI-CLASS-11", "唐詩三首", "唐詩三首", "level_4"),
                    ("CHI-CLASS-12", "詞三首", "詞三首", "level_4"),
                ],
            },
            {
                "name_en": "Modern Chinese Reading",
                "name_zh": "現代文閱讀",
                "syllabus_ref": "Paper 1",
                "knowledge_points": [
                    ("CHI-MOD-01", "Comprehension strategies", "閱讀理解策略", "level_3"),
                ],
            },
            {
                "name_en": "Chinese Writing",
                "name_zh": "寫作",
                "syllabus_ref": "Paper 2",
                "knowledge_points": [
                    ("CHI-WRT-01", "Understanding the prompt", "審題立意", "level_4"),
                    ("CHI-WRT-02", "Narrative and lyrical writing", "記敘抒情", "level_4"),
                    ("CHI-WRT-03", "Argumentative writing", "議論說明", "level_5"),
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
                    ("ENG-WRT-01", "Argumentative essay", "議論文", "level_4"),
                    ("ENG-WRT-02", "Narrative writing", "敘事文", "level_4"),
                    ("ENG-WRT-03", "Content and ideas", "內容構思", "level_4"),
                    ("ENG-WRT-04", "Language accuracy", "語言準確", "level_3"),
                    ("ENG-WRT-05", "Organization", "組織結構", "level_4"),
                ],
            },
            {
                "name_en": "Reading",
                "name_zh": "閱讀",
                "syllabus_ref": "Paper 1",
                "knowledge_points": [
                    ("ENG-READ-01", "Reading comprehension", "閱讀理解", "level_3"),
                ],
            },
            {
                "name_en": "Listening",
                "name_zh": "聆聽",
                "syllabus_ref": "Paper 3",
                "knowledge_points": [
                    ("ENG-LIS-01", "Note-taking", "筆記技巧", "level_3"),
                    ("ENG-LIS-02", "Inference", "推論", "level_4"),
                ],
            },
            {
                "name_en": "Speaking",
                "name_zh": "說話",
                "syllabus_ref": "Paper 4",
                "knowledge_points": [
                    ("ENG-SPK-01", "Group interaction", "小組討論", "level_4"),
                ],
            },
        ],
    },
]


def seed() -> None:
    app = create_app()
    with app.app_context():
        added_subjects = added_topics = added_kps = 0

        for subj_data in SUBJECTS:
            subject = Subject.query.filter_by(code=subj_data["code"]).first()
            if not subject:
                subject = Subject(
                    code=subj_data["code"],
                    name_en=subj_data["name_en"],
                    name_zh=subj_data["name_zh"],
                )
                db.session.add(subject)
                db.session.flush()
                added_subjects += 1

            for topic_data in subj_data["topics"]:
                topic = Topic.query.filter_by(
                    subject_id=subject.id, name_en=topic_data["name_en"]
                ).first()
                if not topic:
                    topic = Topic(
                        subject_id=subject.id,
                        name_en=topic_data["name_en"],
                        name_zh=topic_data["name_zh"],
                        syllabus_ref=topic_data.get("syllabus_ref"),
                    )
                    db.session.add(topic)
                    db.session.flush()
                    added_topics += 1

                for code, name_en, name_zh, level in topic_data["knowledge_points"]:
                    kp = KnowledgePoint.query.filter_by(code=code).first()
                    if kp:
                        kp.topic_id = topic.id
                        kp.name_en = name_en
                        kp.name_zh = name_zh
                        kp.dse_level_hint = level
                    else:
                        db.session.add(
                            KnowledgePoint(
                                topic_id=topic.id,
                                code=code,
                                name_en=name_en,
                                name_zh=name_zh,
                                dse_level_hint=level,
                            )
                        )
                        added_kps += 1

        db.session.commit()
        total_kps = KnowledgePoint.query.count()
        print(
            f"Seed complete. added: subjects={added_subjects} topics={added_topics} "
            f"knowledge_points={added_kps} | totals: subjects={Subject.query.count()} "
            f"topics={Topic.query.count()} knowledge_points={total_kps}"
        )


if __name__ == "__main__":
    seed()
