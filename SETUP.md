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
docker compose up -d postgres redis minio
```

This starts:
- Postgres on `localhost:5432` (user: `app`, db: `bdvisual`)
- Redis on `localhost:6379`
- MinIO (S3-compatible) on `localhost:9000`, console at `localhost:9001`

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

```bash
# backend
cd backend && pytest

# mobile
cd mobile && npm test
```

## Common pitfalls

- **Migrations not applied** → `alembic upgrade head`
- **Mobile can't reach backend on physical device** → replace `localhost` with your machine's LAN IP in `EXPO_PUBLIC_API_BASE_URL`
- **S3 uploads failing** → MinIO bucket needs to be created; the dev seed script handles this. If not, log into MinIO console and create `bdvisual-media`.
- **Google sign-in not working in Expo Go** → use a development build (`npx expo prebuild` + run native), not Expo Go, for OAuth
