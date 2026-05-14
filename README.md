# Pinstagram

A Bangladesh-focused place discovery app — Instagram-style visual feed, Google Maps, TripAdvisor reviews, and real transport info (bus, ride-hail, train) all in one.

## Docs

| File | What's in it |
|---|---|
| `DEV.md` | Coding conventions, repo rules, definition of done |
| `PROJECT.md` | Product overview, user roles, MVP scope |
| `ARCHITECTURE.md` | System diagram, auth flow, feed algorithm, directions algorithm |
| `DATA_MODEL.md` | Every table, every column, indexes |
| `API.md` | Every endpoint with request/response shapes |
| `SETUP.md` | Local dev setup, env vars, common pitfalls |
| `BUILD_PLAN.md` | Phased build order |
| `features/` | Feature specs per area |

## Stack

- **Backend:** FastAPI, SQLAlchemy 2.0 async, PostgreSQL + PostGIS, Redis, Alembic
- **Mobile:** React Native (Expo), TypeScript, NativeWind, TanStack Query, Zustand
- **Storage:** S3-compatible (MinIO locally, AWS S3 / R2 in prod)
- **Maps:** Google Maps Platform

## Quick start

See [SETUP.md](SETUP.md).
