"""add_hierarchical_chunking_and_metadata

Revision ID: 0e464616411f
Revises: 1876c4722542
Create Date: 2026-10-24 10:12:36.288067+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import backend.app.models.base


# revision identifiers, used by Alembic.
revision: str = '0e464616411f'
down_revision: Union[str, None] = '1876c4722542'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add hierarchical chunking and metadata columns to document_chunks
    op.add_column(
        'document_chunks',
        sa.Column('parent_chunk_id', backend.app.models.base.GUID(), nullable=True)
    )
    op.add_column(
        'document_chunks',
        sa.Column('chunk_type', sa.String(length=32), server_default='standalone', nullable=False)
    )
    op.add_column(
        'document_chunks',
        sa.Column('section_title', sa.String(length=255), nullable=True)
    )
    op.add_column(
        'document_chunks',
        sa.Column('content_hash', sa.String(length=64), nullable=True)
    )

    # 2. Add foreign key for self-referential parent-child relationship
    op.create_foreign_key(
        'fk_document_chunks_parent_chunk_id',
        'document_chunks',
        'document_chunks',
        ['parent_chunk_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # 3. Create indexes for filtering and relationship traversal
    op.create_index('idx_chunks_parent_id', 'document_chunks', ['parent_chunk_id'], unique=False)
    op.create_index('idx_chunks_chunk_type', 'document_chunks', ['chunk_type'], unique=False)
    op.create_index('idx_chunks_content_hash', 'document_chunks', ['content_hash'], unique=False)

    # 4. Safe data backfill for existing records
    op.execute("UPDATE document_chunks SET section_title = section_header WHERE section_title IS NULL;")
    op.execute("UPDATE document_chunks SET chunk_type = 'standalone' WHERE chunk_type IS NULL;")
    bind = op.get_bind()
    if bind and bind.dialect.name == "postgresql":
        op.execute("UPDATE document_chunks SET content_hash = md5(content) WHERE content_hash IS NULL;")


def downgrade() -> None:
    op.drop_index('idx_chunks_content_hash', table_name='document_chunks')
    op.drop_index('idx_chunks_chunk_type', table_name='document_chunks')
    op.drop_index('idx_chunks_parent_id', table_name='document_chunks')
    op.drop_constraint('fk_document_chunks_parent_chunk_id', 'document_chunks', type_='foreignkey')
    op.drop_column('document_chunks', 'content_hash')
    op.drop_column('document_chunks', 'section_title')
    op.drop_column('document_chunks', 'chunk_type')
    op.drop_column('document_chunks', 'parent_chunk_id')
