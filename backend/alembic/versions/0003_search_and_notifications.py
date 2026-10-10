"""full-text search, notifications, pagination indexes

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-11
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # enum -> text isn't IMMUTABLE (labels can be renamed), which generated
    # columns require. Our labels are fixed, so wrap the cast.
    op.execute("""
        CREATE FUNCTION place_category_text(place_category) RETURNS text
        LANGUAGE sql IMMUTABLE AS $$ SELECT $1::text $$
    """)

    # 'simple' config: no stemming, so mixed English/Bangla names match as typed.
    op.execute("""
        ALTER TABLE places ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('simple', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('simple', coalesce(area, '') || ' ' ||
                                            coalesce(district, '') || ' ' ||
                                            coalesce(place_category_text(category), '')), 'B') ||
            setweight(to_tsvector('simple', coalesce(description, '')), 'C')
        ) STORED
    """)
    op.create_index(
        "ix_places_search_vector", "places", ["search_vector"], postgresql_using="gin"
    )
    op.execute(
        "CREATE INDEX ix_places_name_trgm ON places USING gin (name gin_trgm_ops)"
    )

    op.execute("""
        ALTER TABLE posts ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(caption, ''))) STORED
    """)
    op.create_index(
        "ix_posts_search_vector", "posts", ["search_vector"], postgresql_using="gin"
    )
    op.create_index("ix_posts_hashtags", "posts", ["hashtags"], postgresql_using="gin")
    op.execute("CREATE INDEX ix_users_name_trgm ON users USING gin (name gin_trgm_ops)")

    # Keyset pagination indexes
    op.create_index("ix_places_rating_id", "places", ["avg_rating", "id"])
    op.create_index(
        "ix_reviews_place_created", "reviews", ["place_id", "status", "created_at"]
    )
    op.create_index(
        "ix_post_comments_post_created", "post_comments", ["post_id", "created_at"]
    )
    op.create_index("ix_posts_user_created", "posts", ["user_id", "created_at"])
    op.create_index(
        "ix_saved_places_user_created", "saved_places", ["user_id", "created_at"]
    )
    op.create_index("ix_admin_actions_created", "admin_actions", ["created_at"])

    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "type",
            sa.Enum(
                "like",
                "comment",
                "follow",
                "post_approved",
                "post_rejected",
                "review_approved",
                name="notification_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "place_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("places.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_notifications_user_created", "notifications", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.execute("DROP TYPE IF EXISTS notification_type")
    for name, table in [
        ("ix_admin_actions_created", "admin_actions"),
        ("ix_saved_places_user_created", "saved_places"),
        ("ix_posts_user_created", "posts"),
        ("ix_post_comments_post_created", "post_comments"),
        ("ix_reviews_place_created", "reviews"),
        ("ix_places_rating_id", "places"),
        ("ix_users_name_trgm", "users"),
        ("ix_posts_hashtags", "posts"),
        ("ix_posts_search_vector", "posts"),
        ("ix_places_name_trgm", "places"),
        ("ix_places_search_vector", "places"),
    ]:
        op.drop_index(name, table_name=table)
    op.drop_column("posts", "search_vector")
    op.drop_column("places", "search_vector")
    op.execute("DROP FUNCTION place_category_text(place_category)")
