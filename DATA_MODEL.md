# DATA_MODEL.md

PostgreSQL 15+. All tables have `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `created_at`, `updated_at` unless noted. Use `pgcrypto` extension for UUIDs and `postgis` for geo queries.

## Core tables

### `users`

| column | type | notes |
|---|---|---|
| id | UUID | PK |
| email | TEXT | unique, indexed |
| password_hash | TEXT | nullable (null if OAuth-only) |
| google_id | TEXT | nullable, unique |
| name | TEXT | required |
| bio | TEXT | nullable |
| avatar_url | TEXT | nullable |
| location | TEXT | nullable, free text |
| is_private | BOOLEAN | default false |
| is_verified | BOOLEAN | default false |
| role | ENUM | `'user' \| 'business' \| 'creator' \| 'admin'` |
| is_premium | BOOLEAN | default false |
| premium_until | TIMESTAMPTZ | nullable |
| email_verified | BOOLEAN | default false |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### `follows`

| column | type | notes |
|---|---|---|
| follower_id | UUID | FK users.id |
| followee_id | UUID | FK users.id |
| created_at | TIMESTAMPTZ | |

PK: `(follower_id, followee_id)`. Index on `followee_id`.

### `places`

| column | type | notes |
|---|---|---|
| id | UUID | PK |
| name | TEXT | required |
| category | ENUM | `'hotel' \| 'restaurant' \| 'cafe' \| 'scenic' \| 'historical' \| 'aesthetic'` |
| description | TEXT | nullable |
| address | TEXT | required |
| division | TEXT | e.g. "Dhaka" |
| district | TEXT | e.g. "Dhaka" |
| area | TEXT | e.g. "Banani" |
| location | GEOGRAPHY(POINT) | PostGIS, lat/lng |
| phone | TEXT | nullable |
| website | TEXT | nullable |
| price_tier | ENUM | `'budget' \| 'mid' \| 'luxury'` |
| opening_hours | JSONB | `{ "mon": "10:00-22:00", ... }` |
| amenities | TEXT[] | e.g. `['parking', 'ac', 'wifi']` |
| cover_photo_url | TEXT | nullable |
| claimed_by_user_id | UUID | FK users.id, nullable (business claim) |
| is_verified | BOOLEAN | default false |
| avg_rating | NUMERIC(2,1) | denormalized, 0.0–5.0 |
| review_count | INTEGER | denormalized |
| save_count | INTEGER | denormalized |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

Indexes: `location` (GIST), `category`, `(division, district, area)`, `price_tier`.

### `posts`

User-generated photo/video posts tagged to a place.

| column | type | notes |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK users.id |
| place_id | UUID | FK places.id |
| media_url | TEXT | required |
| media_type | ENUM | `'image' \| 'video'` |
| thumbnail_url | TEXT | for videos |
| caption | TEXT | nullable |
| hashtags | TEXT[] | |
| price_mentioned | INTEGER | nullable, in BDT (taka) |
| rating | SMALLINT | nullable, 1–5 |
| status | ENUM | `'pending' \| 'published' \| 'rejected'` |
| rejection_reason | TEXT | nullable |
| like_count | INTEGER | denormalized, default 0 |
| comment_count | INTEGER | denormalized, default 0 |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

Indexes: `user_id`, `place_id`, `status`, `created_at DESC`.

### `post_likes`

| column | type | notes |
|---|---|---|
| user_id | UUID | FK users.id |
| post_id | UUID | FK posts.id |
| created_at | TIMESTAMPTZ | |

PK: `(user_id, post_id)`. Index on `post_id`.

### `post_comments`

| column | type | notes |
|---|---|---|
| id | UUID | PK |
| post_id | UUID | FK posts.id |
| user_id | UUID | FK users.id |
| body | TEXT | required, min 1 char |
| created_at | TIMESTAMPTZ | |

### `reviews`

Separate from posts. A review is a structured rating + text about a place.

| column | type | notes |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK users.id |
| place_id | UUID | FK places.id |
| rating | SMALLINT | 1–5, required |
| body | TEXT | min 50 chars |
| price_paid | INTEGER | nullable, BDT |
| status | ENUM | `'pending' \| 'published' \| 'rejected'` |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

Unique: `(user_id, place_id)` — one review per place per user.

### `saved_places`

| column | type | notes |
|---|---|---|
| user_id | UUID | FK users.id |
| place_id | UUID | FK places.id |
| created_at | TIMESTAMPTZ | |

PK: `(user_id, place_id)`.

## Transport tables (the "How to Get There" engine)

### `bus_stops`

| column | type | notes |
|---|---|---|
| id | UUID | PK |
| name | TEXT | e.g. "Mohakhali Bus Stand" |
| location | GEOGRAPHY(POINT) | |
| division | TEXT | |
| district | TEXT | |

GIST index on `location`.

### `bus_routes`

| column | type | notes |
|---|---|---|
| id | UUID | PK |
| name | TEXT | e.g. "Route 6" |
| operator | TEXT | nullable |
| stops | UUID[] | ordered array of bus_stop ids |
| typical_fare | INTEGER | BDT, full route |
| typical_duration_min | INTEGER | |

### `train_stations`

| column | type | notes |
|---|---|---|
| id | UUID | PK |
| name | TEXT | |
| location | GEOGRAPHY(POINT) | |
| division | TEXT | |

### `train_schedules`

| column | type | notes |
|---|---|---|
| id | UUID | PK |
| from_station_id | UUID | FK train_stations.id |
| to_station_id | UUID | FK train_stations.id |
| departure_time | TIME | |
| duration_min | INTEGER | |
| fare | INTEGER | BDT |
| days_of_week | INTEGER[] | 0=Sun..6=Sat |

### `transport_fares`

For ride-hail estimation.

| column | type | notes |
|---|---|---|
| id | UUID | PK |
| provider | ENUM | `'uber' \| 'pathao' \| 'obhai'` |
| base_fare | INTEGER | BDT |
| per_km | INTEGER | BDT |
| per_min | INTEGER | BDT |
| updated_at | TIMESTAMPTZ | |

## Moderation

### `reports`

| column | type | notes |
|---|---|---|
| id | UUID | PK |
| reporter_id | UUID | FK users.id |
| target_type | ENUM | `'post' \| 'review' \| 'comment' \| 'user'` |
| target_id | UUID | |
| reason | ENUM | `'nudity' \| 'hate' \| 'violence' \| 'spam' \| 'wrong_location' \| 'fake_review' \| 'other'` |
| notes | TEXT | nullable |
| status | ENUM | `'open' \| 'resolved' \| 'dismissed'` |
| resolved_by | UUID | FK users.id, nullable |
| created_at | TIMESTAMPTZ | |

### `blocks`

| column | type | notes |
|---|---|---|
| blocker_id | UUID | FK users.id |
| blocked_id | UUID | FK users.id |
| created_at | TIMESTAMPTZ | |

PK: `(blocker_id, blocked_id)`.

## Auth support

### `refresh_tokens`

| column | type | notes |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK users.id |
| token_hash | TEXT | SHA256 of the token |
| device_info | TEXT | nullable |
| expires_at | TIMESTAMPTZ | |
| revoked_at | TIMESTAMPTZ | nullable |
| created_at | TIMESTAMPTZ | |

### `email_verifications`

| column | type | notes |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK users.id |
| code | TEXT | 6-digit |
| expires_at | TIMESTAMPTZ | |
| used_at | TIMESTAMPTZ | nullable |

## Denormalization rules

- `places.avg_rating`, `places.review_count`, `places.save_count` — update via service-layer triggers in code, not DB triggers
- `posts.like_count`, `posts.comment_count` — same
- Recalculate nightly via a cron sanity-check job (v2)

## Soft delete

For v1, **hard delete** posts and comments. Soft delete only `users` (set `deleted_at`, keep their content shown as "[deleted user]"). Adds complexity, but legally cleaner for account deletion requests.
