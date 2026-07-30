"""create initial schema

Revision ID: 8decf91d1a62
Revises:
Create Date: 2026-07-30 16:11:09.933440

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8decf91d1a62'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "papers",
        sa.Column("arxiv_id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("published", sa.Date(), nullable=False),
        sa.Column("corpus", sa.Text(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "chunks",
        sa.Column("chunk_id", sa.String(), primary_key=True),
        sa.Column("arxiv_id", sa.String(), sa.ForeignKey("papers.arxiv_id"), nullable=False),
        sa.Column("section_title", sa.String(), nullable=False),
        sa.Column("part_index", sa.Integer(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
    )

    op.create_table(
        "claims",
        sa.Column("claim_hash", sa.String(), primary_key=True),
        sa.Column("arxiv_id", sa.String(), sa.ForeignKey("papers.arxiv_id"), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("section_title", sa.String(), nullable=False),
    )

    op.create_table(
        "entities",
        sa.Column("entity_key", sa.String(), primary_key=True),
        sa.Column("surface_forms", sa.JSON(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("link_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "entity_links",
        sa.Column("entity_key", sa.String(), sa.ForeignKey("entities.entity_key"), primary_key=True),
        sa.Column("arxiv_id", sa.String(), sa.ForeignKey("papers.arxiv_id"), primary_key=True),
        sa.Column("chunk_id", sa.String(), sa.ForeignKey("chunks.chunk_id"), primary_key=True),
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("corpus", sa.Text(), nullable=False),
        sa.Column("papers_processed", sa.Integer(), nullable=False),
        sa.Column("chunks_indexed", sa.Integer(), nullable=False),
        sa.Column("claims_indexed", sa.Integer(), nullable=False),
        sa.Column("entities_upserted", sa.Integer(), nullable=False),
        sa.Column("llm_input_tokens", sa.Integer(), nullable=False),
        sa.Column("llm_output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_cost_usd", sa.Float(), nullable=False),
        sa.Column("cost_per_paper_usd", sa.Float(), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=False),
        sa.Column("failures", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("entity_links")
    op.drop_table("ingestion_runs")
    op.drop_table("entities")
    op.drop_table("claims")
    op.drop_table("chunks")
    op.drop_table("papers")
