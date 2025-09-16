"""Add searchable_text column to organizations

Revision ID: 59a8399724c4
Revises: 01b3de041708
Create Date: 2025-09-16 08:51:17.206532

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "59a8399724c4"
down_revision: Union[str, None] = "01b3de041708"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add searchable_text column to organizations table if it doesn't exist
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'organizations' AND column_name = 'searchable_text'
            ) THEN
                ALTER TABLE organizations ADD COLUMN searchable_text TEXT;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Remove searchable_text column from organizations table
    op.drop_column("organizations", "searchable_text")
