# feed.md — Visual Feed

## What this covers

The home screen scrolling feed of photos and short videos, similar to Instagram or TikTok. Plus the trending and nearby variants.

## Feed types

1. **`/feed`** — personalized mix (default home tab)
2. **`/feed/trending`** — most-liked in last 7 days
3. **`/feed/nearby`** — within radius of user GPS

## Personalized feed algorithm (v1)

For the authenticated user, fetch and interleave:

| bucket | weight | source |
|---|---|---|
| Following | 40% | Posts from `follows.followee_id`, status=published, last 30 days |
| Trending | 30% | Top `like_count` in last 7 days, status=published |
| Nearby | 20% | Posts whose place is within 50km of user (if GPS permission) — else fall through to trending |
| Discovery | 10% | Random posts from places with `avg_rating >= 4.0` |

Dedupe across buckets. Sort the final mix by a simple score:
```
score = (recency_boost * 2) + (like_count * 0.1) + bucket_boost
```
where `recency_boost = 1 / (hours_since_post + 24)`.

Don't over-engineer. This is a SQL query with `UNION` + `ORDER BY score DESC LIMIT 20`, cached in Redis per user for 5 minutes.

## Pagination

Cursor-based. Cursor encodes `(score, post_id)` — opaque base64 to the client.

```
GET /feed?cursor=<b64>&limit=20
→ { items: [...], next_cursor: "..." | null }
```

When `next_cursor` is null, frontend stops requesting.

## Post item shape (what feed returns)

```ts
type FeedPost = {
  id: string
  media_url: string
  media_type: 'image' | 'video'
  thumbnail_url: string | null
  caption: string | null
  hashtags: string[]
  price_mentioned: number | null  // BDT
  created_at: string
  like_count: number
  comment_count: number
  is_liked_by_me: boolean
  is_saved_by_me: boolean       // is the PLACE saved
  author: {
    id: string
    name: string
    avatar_url: string | null
    is_verified: boolean
  }
  place: {
    id: string
    name: string
    category: string
    area: string                // "Banani"
    district: string            // "Dhaka"
    avg_rating: number
  }
}
```

## Frontend behavior

- Vertical scroll feed, one post fills the screen (TikTok-style) for `media_type=video`, gallery-style for images
- Videos autoplay muted when in view, pause when scrolled away
- Double-tap → like (optimistic)
- Heart icon → like (optimistic)
- Bookmark icon → save the *place* (not the post)
- Tap place name → navigate to place detail screen
- Tap author → navigate to user profile
- Pull-to-refresh at top
- Infinite scroll: prefetch next page when 5 posts from end

## Empty / error states

- **No internet** — show cached posts from React Query + a "you're offline" banner
- **Empty feed** (new user with no follows, GPS denied) — show trending instead, with a "follow some people to personalize this" CTA
- **Error** — show retry button

## Blocked content

The feed query must filter out:
- Posts by users in `blocks` where `blocker_id = me`
- Posts by users who blocked me (`blocked_id = me`)
- Posts with `status != 'published'`
- Posts from users with `deleted_at IS NOT NULL`

## Files to create

**Backend**
- `app/api/v1/feed.py`
- `app/services/feed_service.py` — bucket queries, scoring, caching
- `app/schemas/feed.py`

**Frontend**
- `app/(tabs)/index.tsx` — home / feed screen
- `components/FeedItem.tsx`
- `components/VideoPlayer.tsx` — auto-pause when off-screen
- `lib/api/feed.ts`
- `lib/hooks/useFeed.ts` — TanStack Query infinite query

## Acceptance criteria

- [ ] Feed loads on app open in under 2 seconds (cached)
- [ ] Infinite scroll works without duplicates
- [ ] Like and save are optimistic (instant UI update, rollback on error)
- [ ] Videos autoplay/pause based on viewport
- [ ] Pull-to-refresh works
- [ ] No blocked users' content appears
- [ ] Empty state shows trending fallback
- [ ] Returns 20 items per page

## Out of scope (v1)

- ML-based ranking
- Watch-time signals
- Personalized recommendations beyond the simple bucket mix
- Stories
- Reels-style full-screen video feed (keep mixed for v1)
