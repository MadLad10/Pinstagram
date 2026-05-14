# API.md

All endpoints prefixed `/api/v1`. JSON request/response. Auth via `Authorization: Bearer <jwt>` unless marked `[public]`.

## Conventions

- Cursor pagination: `?cursor=<opaque>&limit=20`. Response: `{ items: [...], next_cursor: "..." | null }`
- Errors: HTTP status + `{ "detail": "human readable" }`
- Timestamps: ISO 8601 UTC (`2025-01-15T10:30:00Z`)
- Money: integer, BDT (taka). No decimals.
- Distance: meters. Duration: seconds.

## Auth

### `POST /auth/signup` [public]
```json
// req
{ "email": "x@y.com", "password": "min8chars", "name": "Rahim" }
// res 201
{ "user": {...}, "access_token": "...", "refresh_token": "..." }
```
Triggers email verification code send.

### `POST /auth/login` [public]
```json
// req
{ "email": "x@y.com", "password": "..." }
// res 200
{ "user": {...}, "access_token": "...", "refresh_token": "..." }
```

### `POST /auth/google` [public]
```json
// req
{ "id_token": "google_id_token_from_mobile_sdk" }
// res 200
{ "user": {...}, "access_token": "...", "refresh_token": "..." }
```

### `POST /auth/refresh` [public]
```json
// req
{ "refresh_token": "..." }
// res 200
{ "access_token": "...", "refresh_token": "..." }
```

### `POST /auth/logout`
Revokes the current refresh token. 204.

### `POST /auth/verify-email` [public]
```json
// req
{ "email": "...", "code": "123456" }
// res 200
{ "verified": true }
```

## Users

### `GET /users/me`
Returns current user's full profile.

### `PATCH /users/me`
```json
{ "name?": "...", "bio?": "...", "avatar_url?": "...", "location?": "...", "is_private?": false }
```

### `DELETE /users/me`
Soft-deletes account.

### `GET /users/{user_id}`
Public profile. Respects `is_private` (returns 403 if private and not a follower).

### `POST /users/{user_id}/follow`
204. Idempotent.

### `DELETE /users/{user_id}/follow`
204.

### `GET /users/{user_id}/followers?cursor=`
### `GET /users/{user_id}/following?cursor=`

### `POST /users/{user_id}/block`
### `DELETE /users/{user_id}/block`

## Places

### `GET /places` [public]
Query params:
- `category` — hotel, restaurant, cafe, scenic, historical, aesthetic
- `division`, `district`, `area`
- `price_tier` — budget, mid, luxury
- `near_lat`, `near_lng`, `radius_m` (default 5000)
- `min_rating` — float
- `amenities` — comma-separated
- `q` — text search on name
- `cursor`, `limit`

Response: paginated list of place summaries (id, name, category, cover_photo_url, avg_rating, price_tier, distance_m if `near_*` supplied).

### `GET /places/{place_id}` [public]
Full place details including amenities, hours, recent reviews, recent posts.

### `POST /places/{place_id}/save`
### `DELETE /places/{place_id}/save`

### `GET /places/{place_id}/posts?cursor=`
Posts tagged to this place. Only `status=published`.

### `GET /places/{place_id}/reviews?cursor=`

### `POST /places/{place_id}/reviews`
```json
{ "rating": 5, "body": "min 50 chars...", "price_paid?": 450 }
```

### `GET /places/{place_id}/directions`
**The killer endpoint.** Query params:
- `from_lat`, `from_lng` (required)

Response:
```json
{
  "distance_m": 8500,
  "options": [
    {
      "mode": "bus",
      "steps": [
        { "type": "walk", "to": "Mohakhali Bus Stand", "distance_m": 1000, "duration_s": 720 },
        { "type": "bus", "route_name": "Route 6", "from": "Mohakhali", "to": "Banani", "duration_s": 1500, "fare": 40 },
        { "type": "walk", "to": "destination", "distance_m": 400, "duration_s": 300 }
      ],
      "total_cost": 40,
      "total_duration_s": 2520,
      "label": "Cheapest"
    },
    {
      "mode": "ride_hail",
      "providers": [
        { "name": "uber", "cost_low": 200, "cost_high": 250, "duration_s": 1080 },
        { "name": "pathao", "cost_low": 180, "cost_high": 230, "duration_s": 1080 }
      ],
      "label": "Fastest"
    },
    {
      "mode": "train",
      "from_station": "Kamalapur",
      "to_station": "...",
      "fare": 50,
      "duration_s": 1500
    },
    {
      "mode": "walk",
      "duration_s": 6300,
      "recommended": false
    }
  ]
}
```

### `GET /places/{place_id}/nearby-hubs`
Returns nearest bus stops and train stations.

## Posts

### `POST /uploads/presign`
```json
// req
{ "filename": "photo.jpg", "content_type": "image/jpeg", "size": 1234567 }
// res
{ "upload_url": "https://s3...", "file_key": "uploads/abc.jpg", "expires_at": "..." }
```

### `POST /posts`
```json
{
  "place_id": "uuid",
  "file_key": "uploads/abc.jpg",
  "media_type": "image",
  "caption": "...",
  "hashtags": ["dhakafood"],
  "price_mentioned": 450,
  "rating": 5
}
```
Returns post with `status: "pending"`.

### `GET /posts/{post_id}` [public if published]

### `DELETE /posts/{post_id}`
Only by author.

### `POST /posts/{post_id}/like` (204, idempotent)
### `DELETE /posts/{post_id}/like`

### `GET /posts/{post_id}/comments?cursor=`

### `POST /posts/{post_id}/comments`
```json
{ "body": "..." }
```

### `DELETE /posts/{post_id}/comments/{comment_id}`

## Feed

### `GET /feed?cursor=&limit=20`
Personalized feed. See ARCHITECTURE.md for the mix.

### `GET /feed/trending?cursor=` [public]
Most-liked posts in last 7 days.

### `GET /feed/nearby?lat=&lng=&radius_m=50000&cursor=`

## Saved

### `GET /me/saved-places?cursor=`

## Search

### `GET /search?q=&type=`
`type` = `places | posts | users | hashtags | all`.

## Reports

### `POST /reports`
```json
{ "target_type": "post", "target_id": "uuid", "reason": "spam", "notes?": "..." }
```

## Admin

All under `/admin/*`, require `role=admin`.

### `GET /admin/posts/pending?cursor=`
### `POST /admin/posts/{post_id}/approve`
### `POST /admin/posts/{post_id}/reject` `{ "reason": "..." }`
### `GET /admin/reports?status=open&cursor=`
### `POST /admin/reports/{report_id}/resolve` `{ "action": "remove_content" | "ban_user" | "dismiss" }`
### `POST /admin/places` — create new place
### `PATCH /admin/places/{place_id}`
### `POST /admin/bus-routes` / `POST /admin/bus-stops` / `POST /admin/train-schedules` — transport data CRUD

## Rate limits (v1)

Implement with Redis:
- Auth endpoints: 10/min/IP
- Post creation: 5/day/user (free), unlimited (premium)
- Comment creation: 30/min/user
- Other writes: 60/min/user
- Reads: 600/min/user

Return 429 with `Retry-After` header.
