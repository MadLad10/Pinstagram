# BUILD_PLAN.md — Order of operations for Claude Code

Build in this order. Don't skip ahead. Each step has a verifiable output.

## Phase 0 — Scaffolding

1. Create monorepo structure per `CLAUDE.md`
2. Set up `backend/` with FastAPI, SQLAlchemy, Alembic, Pydantic, pytest, ruff
3. Set up `mobile/` with Expo + TypeScript + NativeWind + TanStack Query + Zustand
4. Set up `docker-compose.yml` for Postgres, Redis, MinIO
5. Create `.env.example` files
6. First commit: empty app boots, `/healthz` returns 200, Expo shows "Hello" screen

**Done when:** `docker compose up` + backend starts + mobile shows hello screen.

## Phase 1 — Auth

Read `features/auth.md`.

1. Create models: `User`, `RefreshToken`, `EmailVerification`
2. Alembic migration
3. Implement `/auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/verify-email`
4. Mobile screens: login, signup, verify-email
5. Zustand auth store, SecureStore persistence
6. Auth interceptor in API client (auto-refresh on 401)

**Done when:** can sign up, log in, restart app, still logged in.

## Phase 2 — Places (read-only)

Read `features/place-details.md`.

1. Create `Place` model with PostGIS `location` column
2. Migrations + enable `postgis` extension
3. Seed script with 20 demo places across Dhaka
4. `GET /places` (list + filter) and `GET /places/{id}` endpoints
5. Mobile: place detail screen with hero + key info (no directions yet)

**Done when:** can browse seeded places on mobile.

## Phase 3 — Feed (read-only)

Read `features/feed.md`.

1. Create `Post`, `PostLike`, `PostComment` models
2. Seed script adds posts to existing places
3. `GET /feed`, `/feed/trending`, `/feed/nearby` endpoints
4. Mobile: home feed screen with infinite scroll
5. Tap post → navigates to place

**Done when:** can scroll feed of seeded posts, tap to view place.

## Phase 4 — Social (follow, like, comment, save)

Read `features/social.md`.

1. Create `follows`, `saved_places`, `blocks` tables
2. Endpoints: follow/unfollow, like/unlike, comments CRUD, save/unsave
3. Mobile: like button, comment sheet, save button, profile screens with followers/following
4. Notifications table + in-app notification list

**Done when:** can follow another user, like their posts, comment, save places.

## Phase 5 — Posting + media

Read `features/posting.md`.

1. Set up MinIO bucket and S3 presigning
2. `POST /uploads/presign` and `POST /posts` endpoints
3. Mobile: compose flow (pick → tag place → caption → post)
4. Mobile: image picker integration (`expo-image-picker`)
5. Upload progress UI

**Done when:** can upload a photo from phone, it appears in pending state on profile.

## Phase 6 — Admin & moderation

Read `features/admin.md`.

1. `require_admin` dependency
2. Admin endpoints for posts, reviews, reports
3. Audit log table
4. CLI script to create first admin
5. **Build minimal Next.js dashboard** (separate repo) for moderation
6. Approving a post moves it to `published`, appears in feeds

**Done when:** post can be approved in dashboard and shows up in mobile feed.

## Phase 7 — Reviews

Read `features/reviews.md`.

1. `Review` model + migration
2. Endpoints: write, edit, delete, list
3. Aggregation: update `places.avg_rating` on review approval
4. Mobile: write review screen, reviews list on place page

**Done when:** can write and read reviews; avg rating updates.

## Phase 8 — Search & Map

Read `features/search-and-map.md`.

1. Add `tsvector` columns + GIN indexes to places and posts
2. `GET /search` endpoint
3. Mobile: search tab with debounced input, results tabs
4. Mobile: map tab with Google Maps, pin loading on pan/zoom, filters
5. Recent searches in SecureStore

**Done when:** can search for "cafe banani" and find places; map shows pins.

## Phase 9 — "How to Get There" 🚀

Read `features/place-details.md` (directions section) + `ARCHITECTURE.md` (algorithm).

1. Create `bus_stops`, `bus_routes`, `train_stations`, `train_schedules`, `transport_fares` models
2. Admin CSV import for bus data
3. Admin manually inputs 5-10 bus routes for Dhaka
4. `GET /places/{id}/directions` endpoint with bus, ride-hail, train, walking logic
5. Google Directions API client for ride-hail ETA
6. Mobile: "How to Get There" UI on place detail
7. Uber and Pathao deep links

**Done when:** stand at one Dhaka place, view another, see bus route with fare + Uber estimate.

## Phase 10 — Polish & launch prep

1. Error handling on every screen
2. Loading skeletons everywhere
3. Empty states
4. Rate limiting (Redis-backed)
5. Image optimization (thumbnails, lazy loading)
6. Crash reporting (Sentry)
7. Analytics (PostHog or similar)
8. App icons, splash screen
9. Privacy policy, terms of service pages
10. App store / Play Store submission

## Things deferred to v2 (don't build yet)

- Premium subscription + payments
- Hotel/restaurant booking
- Cost calculator
- Multi-stop route planner
- Offline maps
- Push notifications
- Business owner dashboard
- Creator monetization
- Bangla localization
- ML-based feed ranking

When tempted to add one of these in v1, resist. Ship v1 first.
