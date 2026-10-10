# SETUP.md — Local Development Setup

How to bring up the project locally on a fresh machine.

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker + Docker Compose
- Expo CLI (`npm i -g expo-cli`)
- An Android emulator or iOS simulator (or Expo Go on a phone)

## Step 1 — Clone and prep

```bash
git clone <repo>
cd <repo>
cp backend/.env.example backend/.env
cp mobile/.env.example mobile/.env
```

## Step 2 — Bring up services

```bash
docker compose up -d postgres redis s3
```

This starts:
- Postgres on `localhost:5432` (user: `app`, db: `bdvisual`)
- Redis on `localhost:6379`
- SeaweedFS (S3-compatible object storage) on `localhost:9000`. MinIO stopped
  publishing free Docker images in 2025; any S3-compatible store works.

## Step 3 — Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m app.scripts.seed_dev   # seeds a few places, bus routes, demo user
uvicorn app.main:app --reload --port 8000
```

API docs at http://localhost:8000/docs (FastAPI auto-generates Swagger UI).

## Step 4 — Create your admin

```bash
python -m app.scripts.create_admin --email admin@example.com --password admin12345
```

## Step 5 — Mobile

```bash
cd mobile
npm install
npx expo start
```

Press `i` for iOS sim, `a` for Android emulator, or scan QR with Expo Go on a real phone.

## Required env vars

### `backend/.env`

```
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/bdvisual
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=<run: openssl rand -hex 32>
JWT_ACCESS_TTL_MIN=15
JWT_REFRESH_TTL_DAYS=30

S3_ENDPOINT=http://localhost:9000
S3_REGION=us-east-1
S3_BUCKET=bdvisual-media
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin

GOOGLE_OAUTH_CLIENT_ID=<from Google Cloud Console>
GOOGLE_MAPS_API_KEY=<from Google Cloud Console>

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_FROM=no-reply@example.com

ENV=local
```

### `mobile/.env`

```
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
EXPO_PUBLIC_GOOGLE_OAUTH_CLIENT_ID=<from Google Cloud>
EXPO_PUBLIC_GOOGLE_MAPS_API_KEY=<from Google Cloud>
```

## Running tests

The backend tests are integration tests: they run against a real Postgres +
PostGIS (a `bdvisual_test` database is created and migrated automatically) and
Redis, so start `docker compose up -d postgres redis` first.

```bash
cd backend && pytest --cov        # ~85 tests
cd mobile && npm run typecheck
cd admin && npm run build
```

No local Python 3.11+? Run everything in the backend image instead:

```bash
docker compose --profile full build backend
docker compose run --rm -v "$PWD/backend:/app" backend pytest
```

## Demo accounts (after `seed_dev`)

| | email | password |
|---|---|---|
| User | `demo@pinstagram.app` | `demo1234` |
| Admin | `admin@pinstagram.app` | `admin1234` |

Without SMTP configured, verification emails are printed to the API log.

## Common pitfalls

- **Migrations not applied** → `alembic upgrade head`
- **Mobile can't reach backend on physical device** → replace `localhost` with your machine's LAN IP in `EXPO_PUBLIC_API_BASE_URL`
- **S3 uploads failing** → the bucket is created by the dev seed script. On a physical
  phone, set `S3_PUBLIC_URL=http://<your-LAN-IP>:9000` in `backend/.env` so presigned
  upload URLs point somewhere the phone can reach.
- **Expo Go says the project is incompatible** → the app targets Expo SDK 57; update Expo Go.
- **Google sign-in not working in Expo Go** → use a development build (`npx expo prebuild` + run native), not Expo Go, for OAuth
