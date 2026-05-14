"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-14

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute("CREATE TYPE user_role AS ENUM ('user', 'business', 'creator', 'admin')")
    op.execute("CREATE TYPE place_category AS ENUM ('hotel', 'restaurant', 'cafe', 'scenic', 'historical', 'aesthetic')")
    op.execute("CREATE TYPE price_tier AS ENUM ('budget', 'mid', 'luxury')")
    op.execute("CREATE TYPE media_type AS ENUM ('image', 'video')")
    op.execute("CREATE TYPE post_status AS ENUM ('pending', 'published', 'rejected')")
    op.execute("CREATE TYPE review_status AS ENUM ('pending', 'published', 'rejected')")
    op.execute("CREATE TYPE report_target_type AS ENUM ('post', 'review', 'comment', 'user')")
    op.execute("CREATE TYPE report_reason AS ENUM ('nudity', 'hate', 'violence', 'spam', 'wrong_location', 'fake_review', 'other')")
    op.execute("CREATE TYPE report_status AS ENUM ('open', 'resolved', 'dismissed')")
    op.execute("CREATE TYPE ridehail_provider AS ENUM ('uber', 'pathao', 'obhai')")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=True),
        sa.Column("google_id", sa.String, nullable=True, unique=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column("location", sa.String, nullable=True),
        sa.Column("is_private", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("role", sa.Enum("user", "business", "creator", "admin", name="user_role"), nullable=False, server_default="user"),
        sa.Column("is_premium", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("premium_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("device_info", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "email_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(6), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "places",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("category", sa.Enum("hotel", "restaurant", "cafe", "scenic", "historical", "aesthetic", name="place_category"), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("address", sa.Text, nullable=False),
        sa.Column("division", sa.String, nullable=True),
        sa.Column("district", sa.String, nullable=True),
        sa.Column("area", sa.String, nullable=True),
        sa.Column("location", geoalchemy2.Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("phone", sa.String, nullable=True),
        sa.Column("website", sa.String, nullable=True),
        sa.Column("price_tier", sa.Enum("budget", "mid", "luxury", name="price_tier"), nullable=True),
        sa.Column("opening_hours", postgresql.JSONB, nullable=True),
        sa.Column("amenities", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("cover_photo_url", sa.Text, nullable=True),
        sa.Column("claimed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("avg_rating", sa.Numeric(2, 1), nullable=False, server_default="0"),
        sa.Column("review_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("save_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_places_location", "places", ["location"], postgresql_using="gist")
    op.create_index("ix_places_category", "places", ["category"])

    op.create_table(
        "posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("place_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("places.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_url", sa.Text, nullable=False),
        sa.Column("media_type", sa.Enum("image", "video", name="media_type"), nullable=False),
        sa.Column("thumbnail_url", sa.Text, nullable=True),
        sa.Column("caption", sa.Text, nullable=True),
        sa.Column("hashtags", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("price_mentioned", sa.Integer, nullable=True),
        sa.Column("rating", sa.SmallInteger, nullable=True),
        sa.Column("status", sa.Enum("pending", "published", "rejected", name="post_status"), nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("like_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("comment_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_posts_user_id", "posts", ["user_id"])
    op.create_index("ix_posts_place_id", "posts", ["place_id"])
    op.create_index("ix_posts_status", "posts", ["status"])
    op.create_index("ix_posts_created_at", "posts", ["created_at"])

    op.create_table(
        "post_likes",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.Text, nullable=False),
    )
    op.create_index("ix_post_likes_post_id", "post_likes", ["post_id"])

    op.create_table(
        "post_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
    )
    op.create_index("ix_post_comments_post_id", "post_comments", ["post_id"])

    op.create_table(
        "follows",
        sa.Column("follower_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("followee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.Text, nullable=False),
    )
    op.create_index("ix_follows_followee_id", "follows", ["followee_id"])

    op.create_table(
        "saved_places",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("place_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("places.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.Text, nullable=False),
    )

    op.create_table(
        "blocks",
        sa.Column("blocker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("blocked_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.Text, nullable=False),
    )

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("place_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("places.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.SmallInteger, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("price_paid", sa.Integer, nullable=True),
        sa.Column("status", sa.Enum("pending", "published", "rejected", name="review_status"), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_unique_constraint("uq_reviews_user_place", "reviews", ["user_id", "place_id"])

    op.create_table(
        "bus_stops",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("location", geoalchemy2.Geography(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("division", sa.String, nullable=True),
        sa.Column("district", sa.String, nullable=True),
    )
    op.create_index("ix_bus_stops_location", "bus_stops", ["location"], postgresql_using="gist")

    op.create_table(
        "bus_routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("operator", sa.String, nullable=True),
        sa.Column("stops", postgresql.ARRAY(postgresql.UUID(as_uuid=False)), nullable=False),
        sa.Column("typical_fare", sa.Integer, nullable=False),
        sa.Column("typical_duration_min", sa.Integer, nullable=False),
    )

    op.create_table(
        "train_stations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("location", geoalchemy2.Geography(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("division", sa.String, nullable=True),
    )
    op.create_index("ix_train_stations_location", "train_stations", ["location"], postgresql_using="gist")

    op.create_table(
        "train_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("from_station_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("train_stations.id"), nullable=False),
        sa.Column("to_station_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("train_stations.id"), nullable=False),
        sa.Column("departure_time", sa.Time, nullable=False),
        sa.Column("duration_min", sa.Integer, nullable=False),
        sa.Column("fare", sa.Integer, nullable=False),
        sa.Column("days_of_week", postgresql.ARRAY(sa.Integer), nullable=False),
    )

    op.create_table(
        "transport_fares",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("provider", sa.Enum("uber", "pathao", "obhai", name="ridehail_provider"), nullable=False),
        sa.Column("base_fare", sa.Integer, nullable=False),
        sa.Column("per_km", sa.Integer, nullable=False),
        sa.Column("per_min", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", sa.Enum("post", "review", "comment", "user", name="report_target_type"), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Enum("nudity", "hate", "violence", "spam", "wrong_location", "fake_review", "other", name="report_reason"), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("status", sa.Enum("open", "resolved", "dismissed", name="report_status"), nullable=False, server_default="open"),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
    )

    op.create_table(
        "admin_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("target_type", sa.Text, nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
    )


def downgrade() -> None:
    for table in ["admin_actions", "reports", "transport_fares", "train_schedules", "train_stations",
                  "bus_routes", "bus_stops", "reviews", "blocks", "saved_places", "follows",
                  "post_comments", "post_likes", "posts", "places", "email_verifications",
                  "refresh_tokens", "users"]:
        op.drop_table(table)

    for enum in ["user_role", "place_category", "price_tier", "media_type", "post_status",
                 "review_status", "report_target_type", "report_reason", "report_status", "ridehail_provider"]:
        op.execute(f"DROP TYPE IF EXISTS {enum}")
