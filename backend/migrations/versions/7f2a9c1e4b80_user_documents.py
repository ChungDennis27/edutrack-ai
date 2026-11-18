"""user documents

Revision ID: 7f2a9c1e4b80
Revises: 3d3efa20be1f
Create Date: 2026-11-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "7f2a9c1e4b80"
down_revision = "3d3efa20be1f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=80), nullable=False),
        sa.Column("subject", sa.String(length=20), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_user_documents_size_nonneg"),
    )
    with op.batch_alter_table("user_documents", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_user_documents_user_id"), ["user_id"], unique=False)
        batch_op.create_index(
            "ix_user_documents_user_created", ["user_id", "created_at"], unique=False
        )


def downgrade():
    with op.batch_alter_table("user_documents", schema=None) as batch_op:
        batch_op.drop_index("ix_user_documents_user_created")
        batch_op.drop_index(batch_op.f("ix_user_documents_user_id"))
    op.drop_table("user_documents")
