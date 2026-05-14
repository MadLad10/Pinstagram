# admin.md — Admin & Moderation

## What this covers

Admin-only routes and screens for content moderation, place verification, and transport data management. v1 admin is a **separate web dashboard** (not in the mobile app) to keep mobile lean.

## Roles

- Only `users.role='admin'` can access `/admin/*` endpoints
- Backend dependency: `require_admin` raises 403 otherwise

## Admin dashboard (web)

Tech: Next.js (separate repo or `/admin` folder), uses the same backend API. Keep it minimal — Tailwind + shadcn/ui is fine. No need for fancy design.

### Screens

1. **Pending posts queue**
   - Grid of pending posts with media + caption + place + author
   - Approve / Reject (with reason dropdown)
   - Keyboard shortcuts: A = approve, R = reject

2. **Pending reviews queue**
   - List with text body, rating, place
   - Approve / Reject

3. **Reports inbox**
   - All `reports` with `status='open'`
   - Click → see reported content
   - Actions: Remove content / Ban user / Dismiss

4. **Pending places**
   - User-added places awaiting verification
   - Fix name, category, address, GPS if needed
   - Approve / Reject

5. **Transport data**
   - CRUD for bus stops, bus routes, train stations, train schedules, ride-hail fare table
   - Bulk import via CSV (v1) — most data will start as CSV imports

6. **Users**
   - Search by email or name
   - View posts, reviews, reports against them
   - Ban / Unban
   - Promote to creator/business/admin

## Endpoints

See API.md `/admin/*` section. All require `role=admin`.

## Moderation queue behavior

- Posts and reviews enter queue with `status='pending'`
- Admin approves → `status='published'`, becomes visible
- Admin rejects → `status='rejected'`, optionally notifies user with reason
- Banned users: set `users.deleted_at` and `banned_at`. All their content stays hidden. They cannot log in.

## Audit log

For v1, log every admin action to `admin_actions` table:

| column | type |
|---|---|
| id | UUID PK |
| admin_id | UUID FK users.id |
| action | TEXT |
| target_type | TEXT |
| target_id | UUID |
| metadata | JSONB |
| created_at | TIMESTAMPTZ |

Display in dashboard under "Recent activity".

## Initial admin

- First admin user is created via a one-off CLI command: `python -m app.scripts.create_admin --email x@y.com`
- Don't expose admin promotion via API for v1 — promote through DB or script

## Files to create

**Backend**
- `app/api/v1/admin/` — subpackage with one file per resource (`posts.py`, `reviews.py`, `reports.py`, `places.py`, `transport.py`, `users.py`)
- `app/core/deps.py` — `require_admin` dependency
- `app/services/admin_service.py` — audit log helper
- `app/scripts/create_admin.py`

**Admin dashboard (Next.js, separate)**
- Standard Next.js app with API client pointing to the same FastAPI backend
- Auth: admin signs in with email/password through the same `/auth/login`, frontend checks `role=admin` after login

## Acceptance criteria

- [ ] Non-admins get 403 on all `/admin/*` routes
- [ ] Admin can approve/reject posts and reviews
- [ ] Bulk approve (select multiple → approve) works
- [ ] Rejection reasons are required and shown to the user
- [ ] Banned users cannot log in (return generic 401)
- [ ] All admin actions logged
- [ ] CSV import for bus routes/stops works without breaking on bad rows (skip + report errors)

## Out of scope (v1)

- Automated moderation (NSFW detection, spam ML) — humans only
- Granular permissions (different admin levels) — flat admin role
- Multi-language admin UI
- Mobile admin app
