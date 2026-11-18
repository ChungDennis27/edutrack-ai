"""micro lessons

Revision ID: b7e1d4a90c22
Revises: 7f2a9c1e4b80
Create Date: 2026-11-18 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b7e1d4a90c22"
down_revision = "7f2a9c1e4b80"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "micro_lessons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_point_id", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.Integer(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("example_json", sa.Text(), nullable=False),
        sa.Column("sources_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["quiz_attempts.id"]),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("micro_lessons", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_micro_lessons_user_id"), ["user_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_micro_lessons_knowledge_point_id"),
            ["knowledge_point_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_micro_lessons_user_kp_created",
            ["user_id", "knowledge_point_id", "created_at"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("micro_lessons", schema=None) as batch_op:
        batch_op.drop_index("ix_micro_lessons_user_kp_created")
        batch_op.drop_index(batch_op.f("ix_micro_lessons_knowledge_point_id"))
        batch_op.drop_index(batch_op.f("ix_micro_lessons_user_id"))
    op.drop_table("micro_lessons")
