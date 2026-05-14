# posting.md — Posting Photos & Videos

## What this covers

User uploads a photo or video, tags it to a place, adds caption/hashtags/rating, submits. Post goes through moderation before appearing in feeds.

## Flow

1. User taps **+** button (bottom tab bar, center)
2. Choose source: **Take Photo / Take Video / Pick from Gallery**
3. Image picker / camera opens
4. After capture/pick → **Compose screen**
5. On compose screen:
   - Preview of media
   - **Where was this?** — required
     - Auto-detect via GPS reverse-geocode to a Place
     - "Pick a place" search → autocomplete places
     - "I don't see it" → opens "Add new place" mini-form (creates place with `is_verified=false`, goes to admin queue)
   - **Caption** — optional, max 500 chars
   - **Hashtags** — chips, max 10, lowercase, no spaces
   - **Price** — optional integer (BDT)
   - **Rating** — optional 1–5 stars
6. Tap **Post**
7. App uploads media using presigned URL flow (see ARCHITECTURE.md)
8. Then `POST /posts` with metadata + `file_key`
9. Show success toast: "Posted! It'll appear once approved (usually within a few hours)."

## Limits

- Free user: 5 posts/day (rate limit returns 429)
- Premium user: unlimited
- Media file: ≤ 50 MB
- Image dimensions: backend stores original + generates a 1080px max-dim version
- Video: ≤ 60 seconds, ≤ 50 MB, transcoded to H.264 720p (v1: skip transcoding, just validate; transcoding in v2)

## Moderation

- All posts created with `status='pending'`
- Admin queue at `GET /admin/posts/pending`
- Admin approves → `status='published'`, appears in feeds
- Admin rejects → `status='rejected'`, user gets a notification with reason
- Auto-publish v2: trusted users (≥10 approved posts, no rejections in 30 days) skip moderation

For v1: **all posts go through admin**. Yes, this is a bottleneck. Solve it with more admins, not auto-publish, until volume forces a change.

## Upload flow detail

```
[Compose screen]
  ↓ user taps Post
[POST /uploads/presign] → { upload_url, file_key }
  ↓
[PUT upload_url + raw bytes] → 200
  ↓
[POST /posts { file_key, place_id, ... }] → { post: {...} }
  ↓
[Show success, navigate back to feed]
```

If upload fails midway: app saves draft locally and offers retry.

## Adding a new place

Mini-form fields:
- Name (required)
- Category (required)
- Address (required, prefilled from reverse geocode)
- GPS location (auto from current photo or current location)

Creates place with `is_verified=false`. Admin reviews in moderation queue. User's post links to it immediately but won't appear in feeds until both place AND post are approved.

## Files to create

**Backend**
- `app/api/v1/uploads.py` (presign)
- `app/api/v1/posts.py` (CRUD)
- `app/services/uploads_service.py` (S3 presigning)
- `app/services/posts_service.py`
- `app/services/moderation_service.py`
- `app/schemas/post.py`, `app/schemas/upload.py`

**Frontend**
- `app/(tabs)/compose.tsx` — entry/picker
- `app/compose/edit.tsx` — compose screen
- `app/compose/add-place.tsx` — new place form
- `components/compose/MediaPreview.tsx`
- `components/compose/PlacePicker.tsx`
- `components/compose/HashtagInput.tsx`
- `components/compose/StarRating.tsx`
- `lib/api/posts.ts`, `lib/api/uploads.ts`
- `lib/hooks/useUpload.ts`

## Acceptance criteria

- [ ] Can pick image from gallery and post
- [ ] Can take photo with camera and post
- [ ] Can take 30-second video and post
- [ ] GPS-based place suggestion works
- [ ] Place search returns relevant results
- [ ] Can create a new place if not in DB
- [ ] Upload shows progress
- [ ] Failed upload offers retry, doesn't lose draft
- [ ] 5/day limit enforced for free users with friendly error
- [ ] Post appears in user's profile (pending state, only visible to author) immediately
- [ ] Post appears in public feeds only after admin approval

## Out of scope (v1)

- Filters and editing tools (basic crop only)
- Multi-photo carousels (one photo or one video per post)
- Tagging other users
- Music/audio overlay for video
- Schedule post for later
- Edit a post after publishing (delete + repost only)
