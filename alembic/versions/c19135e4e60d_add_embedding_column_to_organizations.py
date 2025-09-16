"""Add embedding column to organizations

Revision ID: c19135e4e60d
Revises: 59a8399724c4
Create Date: 2025-09-16 08:52:37.805745

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "c19135e4e60d"
down_revision: Union[str, None] = "59a8399724c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add embedding column to organizations table if it doesn't exist
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'organizations' AND column_name = 'embedding'
            ) THEN
                ALTER TABLE organizations ADD COLUMN embedding VECTOR(384);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Remove embedding column from organizations table
    op.drop_column("organizations", "embedding")
