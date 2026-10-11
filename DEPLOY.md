# Deploying the public demo

The web app goes on **Vercel**. Its API, database, cache and image storage go on
free tiers of other services, because Vercel only serves the frontend:

| Piece | Service | Free tier notes |
|---|---|---|
| Web app (`mobile/`, Expo web export) | Vercel | Static site |
| API (`backend/`, Docker) | Render | Sleeps after 15 min idle; first request then takes ~1 min |
| Postgres + PostGIS | Neon | 0.5 GB |
| Redis (rate limits) | Upstash | 10k commands/day |
| Image storage | Cloudflare R2 | 10 GB, no egress fees |

Allow 30–45 minutes. Do the steps in order, because later steps need values from earlier ones.
Keep a scratch file open to collect the values marked **→ save**.

---

## 1. Neon (database)

1. Sign up at https://neon.tech and create a project (region: Singapore is closest to Bangladesh).
2. On the project dashboard, copy the **connection string**.
   **→ save as `DATABASE_URL`** (looks like `postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require`).
   Use it as-is; the API converts it for its async driver.

PostGIS and pg_trgm are enabled automatically by the first migration.

## 2. Upstash (Redis)

1. Sign up at https://upstash.com → **Create database** (Redis, same region).
2. Copy the **`rediss://...` connection URL** (TLS, with the password in it).
   **→ save as `REDIS_URL`**

## 3. Cloudflare R2 (images)

1. In the Cloudflare dashboard → **R2** → **Create bucket** named `pinstagram-media`.
2. Open the bucket → **Settings** → **Public access** → enable the **r2.dev subdomain**.
   **→ save the public URL as `MEDIA_BASE_URL`** (e.g. `https://pub-abc123.r2.dev`).
3. Same settings page → **CORS policy** → paste this (put in your Vercel URL after step 5;
   `*` is fine to start):
   ```json
   [
     {
       "AllowedOrigins": ["*"],
       "AllowedMethods": ["PUT", "GET"],
       "AllowedHeaders": ["Content-Type"],
       "MaxAgeSeconds": 3600
     }
   ]
   ```
4. R2 overview → **Manage R2 API Tokens** → **Create API token** with *Object Read & Write*
   on this bucket. Copy:
   **→ `S3_ACCESS_KEY`** (Access Key ID), **→ `S3_SECRET_KEY`** (Secret Access Key),
   **→ `S3_ENDPOINT`** (`https://<account-id>.r2.cloudflarestorage.com`).

## 4. Render (API)

1. Sign up at https://render.com with GitHub → **New** → **Blueprint** → select the
   `Pinstagram` repo. Render reads [`render.yaml`](render.yaml).
2. Fill in the prompted values from your scratch file. For `CORS_ORIGINS`, use
   `https://pinstagram.vercel.app` for now; you'll correct it in step 6. Choose a strong
   **`ADMIN_PASSWORD`** and save it.
3. Click **Apply**. The first build takes ~5 minutes. Migrations run on startup.
4. Open `https://<your-service>.onrender.com/readyz`. It should show
   `{"database":"ok","redis":"ok"}`.
   **→ save the base URL as `API_URL`**

### Load the demo data

Render's free plan has no shell, so seed from your own machine, pointed at Neon:

```bash
cd Pinstagram
docker compose --profile full build backend
docker compose run --rm --no-deps \
  -e ENV=production \
  -e JWT_SECRET=unused-for-seeding \
  -e DATABASE_URL='<DATABASE_URL>' \
  -e ADMIN_PASSWORD='<ADMIN_PASSWORD>' \
  -e S3_ENDPOINT='<S3_ENDPOINT>' -e S3_ACCESS_KEY='<S3_ACCESS_KEY>' \
  -e S3_SECRET_KEY='<S3_SECRET_KEY>' -e S3_BUCKET=pinstagram-media -e S3_REGION=auto \
  backend python -m app.scripts.seed_dev
```

On a public deployment only `demo@pinstagram.app` / `demo1234` is a known login. The
admin uses your `ADMIN_PASSWORD`, and the other seeded users get random passwords. The
shared demo account can't be deleted or renamed by visitors.

## 5. Vercel (web app)

1. Sign up at https://vercel.com with GitHub → **Add New** → **Project** → import `Pinstagram`.
2. **Root Directory:** `mobile`. Framework preset: **Other**. Build settings come from
   [`mobile/vercel.json`](mobile/vercel.json), so leave them alone.
3. **Environment Variables:**
   | Name | Value |
   |---|---|
   | `EXPO_PUBLIC_API_BASE_URL` | `<API_URL>/api/v1` |
   | `EXPO_PUBLIC_DEMO_EMAIL` | `demo@pinstagram.app` |
   | `EXPO_PUBLIC_DEMO_PASSWORD` | `demo1234` |
4. **Deploy.** Note the URL, e.g. `https://pinstagram-xyz.vercel.app`.

## 6. Connect them

1. Render → your service → **Environment** → set `CORS_ORIGINS` to your exact Vercel URL
   (no trailing slash; add the admin dashboard URL too, comma-separated, if you deploy it).
   Save, and the service redeploys.
2. Optional: tighten the R2 CORS `AllowedOrigins` to the same URL.
3. Open the Vercel URL → **Try the demo account**. Allow location to see directions from
   where you are (they only cover Dhaka; elsewhere you'll mostly see ride-hail and walking).

## Updating

Pushing to `main` redeploys both Render and Vercel automatically.

## Troubleshooting

- **Login spins for ~a minute** → the free Render instance was asleep. It's fine after the first request.
- **"Network Error" in the browser console** → `CORS_ORIGINS` doesn't exactly match the Vercel URL.
- **Uploads fail** → check the R2 CORS policy and that `S3_ENDPOINT` is the account endpoint, not the public `r2.dev` URL.
- **Images in posts don't load** → `MEDIA_BASE_URL` must be the bucket's public r2.dev URL.
