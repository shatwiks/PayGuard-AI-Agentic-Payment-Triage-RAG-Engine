"""add_investigation_result_modes_and_evidence

Revision ID: c85ee7f3b4bf
Revises: 27f582bc15ef
Create Date: 2026-10-23 20:20:56.406642+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'c85ee7f3b4bf'
down_revision: Union[str, None] = '27f582bc15ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy.dialects.postgresql import JSONB
    json_type = JSONB().with_variant(sa.JSON(), 'sqlite')

    op.add_column(
        'investigation_results',
        sa.Column('retrieval_mode', sa.String(length=32), server_default='hybrid', nullable=False)
    )
    op.add_column(
        'investigation_results',
        sa.Column('generation_mode', sa.String(length=32), server_default='deterministic_fallback', nullable=False)
    )
    op.add_column(
        'investigation_results',
        sa.Column('evidence_package', json_type, nullable=True)
    )


def downgrade() -> None:
    op.drop_column('investigation_results', 'evidence_package')
    op.drop_column('investigation_results', 'generation_mode')
    op.drop_column('investigation_results', 'retrieval_mode')

