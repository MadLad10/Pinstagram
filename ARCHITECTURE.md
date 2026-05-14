# ARCHITECTURE.md

## High level

```
┌─────────────────────┐         ┌──────────────────────┐
│  React Native App   │◄───────►│   FastAPI Backend    │
│  (Expo, TypeScript) │  HTTPS  │   (Python 3.11)      │
└─────────────────────┘         └──────────┬───────────┘
                                           │
              ┌────────────────────────────┼────────────────────────────┐
              │                            │                            │
       ┌──────▼─────┐              ┌───────▼──────┐            ┌────────▼────────┐
       │ PostgreSQL │              │    Redis     │            │  S3 / R2 Bucket │
       │ (main DB)  │              │ (cache,      │            │  (media files)  │
       └────────────┘              │  rate limit) │            └─────────────────┘
                                   └──────────────┘

External APIs:
- Google Maps Platform (Places, Directions, Maps SDK)
- Google OAuth (sign-in)
- bKash / Nagad (later — v2 booking)
```

## Backend layers

Strict layering. Don't skip layers.

```
HTTP Request
   ↓
[Route handler]   ← api/v1/*.py    — thin; validates input, calls service
   ↓
[Service]         ← services/*.py  — business logic, orchestrates models
   ↓
[Model / Repo]    ← models/*.py    — SQLAlchemy, DB access
   ↓
PostgreSQL
```

Rules:
- Handlers never touch the DB directly. They call services.
- Services never return SQLAlchemy models to handlers. They return Pydantic schemas or plain dicts.
- Models never know about HTTP.

## Auth flow

1. User signs up or logs in (email/password OR Google OAuth)
2. Backend returns `{ access_token, refresh_token, user }`
3. Access token: JWT, 15 min expiry, signed HS256
4. Refresh token: JWT, 30 day expiry, stored in DB so it can be revoked
5. Mobile app stores both in **Expo SecureStore** (never AsyncStorage)
6. Every API call sends `Authorization: Bearer <access_token>`
7. On 401, mobile app calls `/auth/refresh` with the refresh token, gets new pair, retries

## Media upload flow

The frontend never sees S3 credentials.

1. User picks a photo/video in the app
2. App calls `POST /uploads/presign` with `{ filename, content_type, size }`
3. Backend returns `{ upload_url, file_key, expires_at }` — a presigned PUT URL
4. App PUTs the file directly to S3 using that URL
5. App calls `POST /posts` with `{ file_key, place_id, caption, ... }`
6. Backend verifies the file exists in S3, creates the post row in DB
7. Post enters **moderation queue** with status `pending`
8. Admin approves → status `published` → appears in feeds

## Feed generation (v1: simple)

For v1, keep it dumb:

1. Pull recent published posts (last 30 days)
2. Mix in this order:
   - 40% from people the user follows
   - 30% trending (most likes in last 7 days)
   - 20% nearby (within 50km of user's GPS, if permission granted)
   - 10% recommended (random from highly-rated places)
3. Cache result in Redis per user for 5 minutes
4. Paginate by cursor (not page number)

Don't build ML ranking in v1. A simple SQL query with a small Redis cache is fine for ~100k users.

## "How to Get There" — how it works

This is the differentiator. Given user GPS + destination GPS:

1. Compute straight-line distance (Haversine)
2. **Bus option** — query `bus_stops` table for stops within 1km of user AND within 1km of destination. Look up `bus_routes` connecting them. Return cheapest viable route with cost from `transport_fares` table.
3. **Ride-hail option** — call Google Directions API (driving mode) for ETA and distance. Estimate cost via formula: `base_fare + per_km_rate * distance + surge`. Per-km rates stored in `transport_fares`.
4. **Train option** — query `train_stations` within 3km of both endpoints. If found, return schedule from `train_schedules`.
5. **Walking** — if straight-line distance < 2km, show as option. Otherwise mark "not recommended".

All transport data is **admin-curated**. Admins add bus routes, stations, and fare rates. Crowdsourced corrections come in v2.

## State management (frontend)

- **Server state** → TanStack Query (caching, refetching, optimistic updates)
- **Auth state** → Zustand store, persisted via SecureStore
- **UI state** (modals, drafts) → local `useState` or Zustand if shared
- **Never** put server data in Zustand. Always Query.

## Background jobs (v1)

Keep simple. FastAPI `BackgroundTasks` for fire-and-forget (sending email verification, generating thumbnails). Add Celery/RQ only when we need scheduled jobs.

## Environments

- `local` — Docker Compose: Postgres + Redis + MinIO (S3-compatible)
- `staging` — single VPS, same stack
- `production` — TBD (Render / Railway / AWS — decide later)
