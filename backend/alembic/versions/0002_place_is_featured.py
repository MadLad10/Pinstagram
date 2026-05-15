"""add is_featured to places

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "places",
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("places", "is_featured")
