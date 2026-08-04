"""add page range to chunks

Revision ID: 3aea73942b6e
Revises: 8decf91d1a62
Create Date: 2026-08-04 17:15:09.313481

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3aea73942b6e'
down_revision: Union[str, Sequence[str], None] = '8decf91d1a62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("chunks", sa.Column("page_start", sa.Integer(), nullable=True))
    op.add_column("chunks", sa.Column("page_end", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("chunks", "page_end")
    op.drop_column("chunks", "page_start")
