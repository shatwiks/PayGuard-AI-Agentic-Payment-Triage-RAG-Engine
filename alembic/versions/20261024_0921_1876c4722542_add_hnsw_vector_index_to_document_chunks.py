"""add_hnsw_vector_index_to_document_chunks

Revision ID: 1876c4722542
Revises: c85ee7f3b4bf
Create Date: 2026-10-24 09:21:04.617259+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1876c4722542'
down_revision: Union[str, None] = 'c85ee7f3b4bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind and bind.dialect.name == "postgresql":
        # Create HNSW index for cosine distance (<=>) over 1536-dimensional vectors
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind and bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS idx_document_chunks_embedding_hnsw;")
