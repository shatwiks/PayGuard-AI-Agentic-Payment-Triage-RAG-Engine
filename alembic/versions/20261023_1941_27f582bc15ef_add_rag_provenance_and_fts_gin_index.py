"""add_rag_provenance_and_fts_gin_index

Revision ID: 27f582bc15ef
Revises: 6b333f722afd
Create Date: 2026-10-23 19:41:23.378884+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '27f582bc15ef'
down_revision: Union[str, None] = '6b333f722afd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add provenance fields to knowledge_documents
    op.add_column('knowledge_documents', sa.Column('source_id', sa.String(length=128), nullable=True))
    op.add_column('knowledge_documents', sa.Column('content_hash', sa.String(length=64), nullable=True))
    op.add_column('knowledge_documents', sa.Column('raw_content', sa.Text(), nullable=True))
    op.create_index('idx_knowledge_docs_source_id', 'knowledge_documents', ['source_id'], unique=False)

    # 2. Add embedding_model to document_chunks
    op.add_column('document_chunks', sa.Column('embedding_model', sa.String(length=64), nullable=True))
    op.create_index('idx_document_chunks_embedding_model', 'document_chunks', ['embedding_model'], unique=False)

    # 3. Add stored generated tsvector column and GIN index in PostgreSQL
    op.execute(
        "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', coalesce(section_header, '') || ' ' || coalesce(content, ''))) STORED;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_chunks_tsv ON document_chunks USING gin(tsv);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_tsv;")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS tsv;")
    op.drop_index('idx_document_chunks_embedding_model', table_name='document_chunks')
    op.drop_column('document_chunks', 'embedding_model')
    op.drop_index('idx_knowledge_docs_source_id', table_name='knowledge_documents')
    op.drop_column('knowledge_documents', 'raw_content')
    op.drop_column('knowledge_documents', 'content_hash')
    op.drop_column('knowledge_documents', 'source_id')
