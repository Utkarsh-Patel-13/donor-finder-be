"""Add organizations and filings tables with searchable_text and embedding

Revision ID: 01b3de041708
Revises:
Create Date: 2025-09-16 08:50:24.680278

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "01b3de041708"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ein", sa.Integer(), nullable=False),
        sa.Column("strein", sa.String(length=12), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=True),
        sa.Column("sub_name", sa.String(length=500), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("zipcode", sa.String(length=15), nullable=True),
        sa.Column("subseccd", sa.Integer(), nullable=True),
        sa.Column("ntee_code", sa.String(length=10), nullable=True),
        sa.Column("guidestar_url", sa.Text(), nullable=True),
        sa.Column("nccs_url", sa.Text(), nullable=True),
        sa.Column("searchable_text", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("irs_updated", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_ein"), "organizations", ["ein"], unique=True)
    op.create_index(op.f("ix_organizations_id"), "organizations", ["id"], unique=False)
    op.create_index(
        op.f("ix_organizations_name"), "organizations", ["name"], unique=False
    )
    op.create_index(
        op.f("ix_organizations_state"), "organizations", ["state"], unique=False
    )
    op.create_index(
        op.f("ix_organizations_strein"), "organizations", ["strein"], unique=False
    )
    op.create_index(
        op.f("ix_organizations_subseccd"), "organizations", ["subseccd"], unique=False
    )

    # Create filings table
    op.create_table(
        "filings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("tax_period", sa.Integer(), nullable=True),
        sa.Column("tax_period_begin", sa.Date(), nullable=True),
        sa.Column("tax_period_end", sa.Date(), nullable=True),
        sa.Column("pdf_url", sa.Text(), nullable=True),
        sa.Column("total_revenue", sa.BigInteger(), nullable=True),
        sa.Column("total_expenses", sa.BigInteger(), nullable=True),
        sa.Column("total_assets", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_filings_id"), "filings", ["id"], unique=False)
    op.create_index(
        op.f("ix_filings_organization_id"), "filings", ["organization_id"], unique=False
    )
    op.create_index(
        op.f("ix_filings_tax_period"), "filings", ["tax_period"], unique=False
    )


def downgrade() -> None:
    # Drop tables
    op.drop_index(op.f("ix_filings_tax_period"), table_name="filings")
    op.drop_index(op.f("ix_filings_organization_id"), table_name="filings")
    op.drop_index(op.f("ix_filings_id"), table_name="filings")
    op.drop_table("filings")

    op.drop_index(op.f("ix_organizations_subseccd"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_strein"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_state"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_name"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_id"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_ein"), table_name="organizations")
    op.drop_table("organizations")
