# DEV.md — Developer Guide

This file documents conventions and architecture for this codebase.

## Project

A mobile app for Bangladesh combining Instagram-style visual discovery, Google Maps, TripAdvisor reviews, and real transport info (bus, ride-hail, train) in one place.

The killer feature is the **"How to Get There"** section on every place page — bus routes, ride-hail estimates, train options, and walking with costs and times. No other app in Bangladesh does this.

## Tech Stack

- **Backend:** FastAPI (Python 3.11+), SQLAlchemy 2.0 async, Alembic, PostgreSQL 15+ with PostGIS, Pydantic v2
- **Mobile:** React Native via Expo (TypeScript)
- **Auth:** JWT (access + refresh tokens)
- **Storage:** S3-compatible (AWS S3 or Cloudflare R2)
- **Maps:** Google Maps Platform (Maps SDK, Places, Directions)
- **Cache:** Redis (feed cache, rate limits)
- **Testing:** pytest (backend), Jest + React Native Testing Library (mobile)

## Repo Structure

```
/
├── backend/
│   ├── app/
│   │   ├── api/v1/      — route handlers per feature
│   │   ├── core/        — config, security, DI deps
│   │   ├── db/          — session, base model
│   │   ├── models/      — SQLAlchemy models
│   │   ├── schemas/     — Pydantic schemas
│   │   ├── services/    — business logic
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
├── mobile/
│   ├── app/             — Expo Router screens
│   ├── components/
│   ├── lib/             — API client, hooks, utils
│   ├── store/           — Zustand state
│   └── package.json
└── features/            — feature specs
```

## Coding Conventions

### Backend (FastAPI)

- Async route handlers everywhere. SQLAlchemy 2.0 async session.
- One router file per resource: `api/v1/places.py`, `api/v1/posts.py`, etc.
- Pydantic schemas in `schemas/`, split into `XCreate`, `XUpdate`, `XRead`.
- Business logic in `services/`, not in route handlers. Handlers are thin.
- Dependency injection for DB session, current user — never import session directly in a handler.
- Raise `HTTPException` with a clear `detail`. Don't return error dicts manually.
- Naming: `snake_case` for Python; table names plural (`users`, `places`); model classes singular (`User`, `Place`).

### Mobile (React Native + Expo)

- TypeScript strict mode.
- File-based routing via Expo Router. Screens in `app/`.
- Server state: TanStack Query. Global state: Zustand. No Redux.
- Styling: NativeWind (Tailwind for RN). Avoid inline `StyleSheet` for new code.
- Components: PascalCase files, default export.
- Hooks: `useX` prefix, in `lib/hooks/`.

### Git

- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.

## Definition of Done

- [ ] Code matches the relevant feature spec in `features/`
- [ ] Tests pass (`pytest` / `npm test`)
- [ ] Lint passes (`ruff` / `eslint`)
- [ ] Alembic migration created if schema changed
- [ ] `API.md` updated if endpoint changed
- [ ] `.env.example` updated if new env var added
