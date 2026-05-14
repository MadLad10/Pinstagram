# reviews.md — Reviews & Ratings

## What this covers

Structured reviews on places: star rating + text. Separate from posts. One review per user per place.

## Differences from posts

| | Post | Review |
|---|---|---|
| Media | Required | Optional |
| Text | Optional caption | Required body, ≥50 chars |
| Rating | Optional | Required |
| Limit | 5/day (free) | One per place per user |
| Where shown | Feed | Place detail page |

## Compose

- Entry: "Write a Review" button on place detail page
- Form:
  - Star rating (1–5, required)
  - Text body (≥50, ≤2000 chars)
  - Price paid (optional, BDT integer)
- Submit → `POST /places/{place_id}/reviews`
- Goes through moderation like posts (`status='pending'`)

## Edit / delete

- Author can edit their own review at any time → `PATCH /reviews/{id}` (resets to `pending`)
- Author can delete → `DELETE /reviews/{id}`
- After deletion, can write a new one

## Display on place page

- Top 3 most recent + most helpful reviews
- "See all reviews" → full list screen, sorted by recency or rating
- Each review card: avatar, name, star rating, date, body, price paid (if set)
- "Report" in overflow

## Rating aggregation

- `places.avg_rating` and `places.review_count` are denormalized
- Updated in `reviews_service` when a review is approved, edited, or deleted
- Only `status='published'` reviews count toward avg

## Files to create

**Backend**
- `app/api/v1/reviews.py`
- `app/services/reviews_service.py` — CRUD + rating recompute
- `app/schemas/review.py`

**Frontend**
- `app/place/[id]/review.tsx` — compose
- `app/place/[id]/reviews.tsx` — full list
- `components/reviews/ReviewCard.tsx`
- `components/reviews/StarRating.tsx` (reuse from posting)
- `lib/api/reviews.ts`

## Acceptance criteria

- [ ] Can write a review for any place
- [ ] Cannot write a second review for same place (404 with clear message; redirect to edit)
- [ ] Star rating required, 1–5 only
- [ ] Body ≥50 chars enforced
- [ ] Place's avg rating updates correctly after approval
- [ ] Can edit own review (re-enters moderation)
- [ ] Can delete own review (avg rating recalculates)
- [ ] Reviews list paginated

## Out of scope (v1)

- "Helpful" votes on reviews
- Reply to reviews (business owners can reply in v2)
- Photos in reviews (use posts for photos)
- Reviewer reputation / badges
