# CLAUDE.md — Instructions for Claude Code

This file tells you how to work on this codebase. Read it first, every session.

## Project

A mobile app for Bangladesh that combines Instagram-style visual discovery + Google Maps + TripAdvisor + Rome2Rio. Users discover hotels, restaurants, cafes, and scenic spots, see real user photos/videos, and get practical transport info on how to reach each place.

The **killer feature** is the "How to Get There" section on every place page — it shows bus routes, ride-hail estimates, train options, and walking, with costs and times. No other app in Bangladesh does this well.

## Tech Stack

- **Backend:** FastAPI (Python 3.11+), SQLAlchemy 2.0, Alembic for migrations, PostgreSQL 15+, Pydantic v2
- **Frontend:** React Native via Expo (TypeScript)
- **Auth:** JWT (access + refresh tokens)
- **Storage:** S3-compatible (AWS S3 or Cloudflare R2) for media
- **Maps:** Google Maps Platform (Maps SDK, Places, Directions)
- **Cache/Queue:** Redis (for feed cache, rate limits, background jobs later)
- **Testing:** pytest (backend), Jest + React Native Testing Library (frontend)

## Repo Structure

```
/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Route handlers grouped by feature
│   │   ├── core/            # Config, security, deps
│   │   ├── db/              # Session, base, migrations
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
├── mobile/
│   ├── app/                 # Expo Router screens
│   ├── components/
│   ├── lib/                 # API client, hooks, utils
│   ├── store/               # State (Zustand)
│   └── package.json
└── docs/                    # Specs — read these before building features
    ├── PROJECT.md
    ├── ARCHITECTURE.md
    ├── DATA_MODEL.md
    ├── API.md
    └── features/
```

## How to work on a task

1. **Read the relevant feature spec first.** If the task touches posting, open `docs/features/posting.md`. If it touches the feed, open `docs/features/feed.md`. Never guess — the spec is the source of truth.
2. **Check `DATA_MODEL.md`** before touching any model or migration.
3. **Check `API.md`** before adding or changing an endpoint. Keep endpoint shapes consistent with what's documented; if you need to change them, update the doc in the same commit.
4. **One feature per PR/commit.** Don't sprawl.
5. **Write the test alongside the code.** Backend: pytest. Frontend: at least one render test per new screen.

## Coding conventions

### Backend (FastAPI)

- Use **async** route handlers everywhere. SQLAlchemy 2.0 async session.
- One router file per resource: `api/v1/places.py`, `api/v1/posts.py`, etc.
- **Pydantic schemas** live in `schemas/`, separated into `XCreate`, `XUpdate`, `XRead` per resource.
- **Business logic** goes in `services/`, not in route handlers. Route handlers should be thin.
- Use **dependency injection** for DB session, current user, etc. — never import the session directly inside a handler.
- Errors: raise `HTTPException` with a clear `detail` string. Don't return error dicts manually.
- Naming: `snake_case` for everything Python; table names plural (`users`, `places`); model classes singular (`User`, `Place`).

### Frontend (React Native + Expo)

- TypeScript strict mode. No `any` unless commented why.
- File-based routing (Expo Router). Screens go in `app/`.
- State: **Zustand** for global state, **React Query (TanStack Query)** for server state. Don't use Redux.
- Styling: NativeWind (Tailwind for RN). Avoid inline `StyleSheet` for new code.
- Components: PascalCase files, default export.
- Hooks: `useX` prefix, in `lib/hooks/`.

### Git / commits

- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
- Reference the spec file in the commit body when relevant.

## Definition of done

A task is done when:
- [ ] Code matches the spec in `docs/features/<feature>.md`
- [ ] Tests pass locally (`pytest` / `npm test`)
- [ ] Lint passes (`ruff` / `eslint`)
- [ ] If schema changed: Alembic migration created
- [ ] If API changed: `docs/API.md` updated
- [ ] If new env var needed: `.env.example` updated

## Things to NEVER do without asking

- Add a new third-party paid service (always check first)
- Change the auth flow
- Add a new top-level dependency in `pyproject.toml` or `package.json` without explaining why
- Delete migrations
- Commit secrets, `.env` files, or API keys

## Things to always do

- Run migrations before claiming a backend task is done
- Handle the loading + error states on every screen (not just the success state)
- Use the user's GPS politely — ask permission, never block the app if denied
- Display all prices in **BDT (৳)**, not USD or INR. The PDF uses ₹ but that's a typo — Bangladesh uses Taka (৳)
- Keep file uploads behind a presigned-URL flow (frontend never sees S3 credentials)
