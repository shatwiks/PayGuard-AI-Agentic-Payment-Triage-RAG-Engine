"""Add user uploaded document metadata, ownership, and tracking fields.

Revision ID: 3f8a91b2c4d5
Revises: 0e464616411f
Create Date: 2026-10-24 16:26:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3f8a91b2c4d5"
down_revision: Union[str, None] = "0e464616411f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add user ownership, isolation, and processing tracking columns
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "uploaded_by_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("file_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("mime_type", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("storage_path", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "processing_status",
            sa.String(length=32),
            server_default=sa.text("'completed'"),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "embedding_status",
            sa.String(length=32),
            server_default=sa.text("'completed'"),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("page_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("chunk_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )

    # 2. Add performance & access control indexes
    op.create_index(
        "idx_docs_uploaded_by_active",
        "knowledge_documents",
        ["uploaded_by_id", "is_active"],
    )
    op.create_index(
        "idx_docs_is_system_active",
        "knowledge_documents",
        ["is_system", "is_active"],
    )
    op.create_index(
        "idx_docs_content_hash_user",
        "knowledge_documents",
        ["content_hash", "uploaded_by_id"],
    )

    # 3. Mark existing seeded documents as authoritative system documents
    op.execute("UPDATE knowledge_documents SET is_system = true WHERE uploaded_by_id IS NULL")


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_docs_content_hash_user", table_name="knowledge_documents")
    op.drop_index("idx_docs_is_system_active", table_name="knowledge_documents")
    op.drop_index("idx_docs_uploaded_by_active", table_name="knowledge_documents")

    # Drop columns
    op.drop_column("knowledge_documents", "chunk_count")
    op.drop_column("knowledge_documents", "page_count")
    op.drop_column("knowledge_documents", "error_message")
    op.drop_column("knowledge_documents", "embedding_status")
    op.drop_column("knowledge_documents", "processing_status")
    op.drop_column("knowledge_documents", "storage_path")
    op.drop_column("knowledge_documents", "mime_type")
    op.drop_column("knowledge_documents", "file_size_bytes")
    op.drop_column("knowledge_documents", "file_name")
    op.drop_column("knowledge_documents", "is_system")
    op.drop_column("knowledge_documents", "uploaded_by_id")
