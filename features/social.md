# social.md — Follow, Like, Comment, Save

## What this covers

The lightweight social layer: follow users, like posts, comment on posts, save places.

## Follow

### Behavior
- Follow button on user profile
- Tap → `POST /users/{id}/follow` (idempotent, 204)
- Untap → `DELETE /users/{id}/follow`
- Optimistic UI: toggle instantly, rollback on error
- Counts on profile update from server response

### Following / Followers lists
- Tap "X followers" → list screen with cursor pagination
- Each row: avatar, name, bio snippet, follow button
- Cannot see private user's followers/following unless you follow them

### Notifications
- New follower → notification entry (in-app only for v1, no push yet)
- "User X started following you"

## Likes

- Heart icon on every post
- Double-tap on post media also likes (with animated heart overlay)
- `POST /posts/{id}/like` and `DELETE /posts/{id}/like`, both idempotent
- Optimistic UI
- `like_count` denormalized on `posts` table — updated in `posts_service`
- Like notifications batched: "User X and 3 others liked your post" if multiple in last hour

## Comments

- Comment button on post → opens comments sheet
- List of comments, newest first
- Compose at bottom
- `POST /posts/{id}/comments` with `{ body }`
- Author can delete their own comment
- Post author can delete any comment on their post
- 30 comments per minute rate limit
- `comment_count` denormalized

### What's NOT in v1
- Threaded replies — flat list only
- Comment likes
- @mentions (just text)

## Save (Place bookmark)

- Bookmark icon on feed posts and place pages
- `POST /places/{id}/save` and `DELETE /places/{id}/save`
- One flat "Saved" list per user — no collections in v1 (deferred per PROJECT.md)
- Saved places visible at `/me/saved-places`

### Saved screen
- Tab in profile
- Grid of saved places (cover photo + name + category)
- Tap → place detail
- Long-press → "Remove from saved"

## Share

- Native share sheet
- Share post: deep link `bdvisual://post/{id}` + fallback web URL `https://app.example.com/post/{id}`
- Share place: same pattern
- Web URL renders an OG-tag preview page (basic HTML, generates dynamic image v2)

## Files to create

**Backend**
- `app/api/v1/users.py` (follow, followers, following endpoints — extends auth user routes)
- `app/api/v1/posts.py` extended for likes & comments
- `app/services/social_service.py` — follow/unfollow logic, follow notifications
- `app/services/interactions_service.py` — likes, comments
- `app/schemas/social.py`

**Frontend**
- `app/profile/[id].tsx` — user profile screen
- `app/profile/[id]/followers.tsx`
- `app/profile/[id]/following.tsx`
- `components/social/FollowButton.tsx`
- `components/social/LikeButton.tsx`
- `components/social/CommentSheet.tsx`
- `components/social/SaveButton.tsx`
- `lib/api/social.ts`
- `lib/hooks/useFollow.ts`, `useLike.ts`, `useSave.ts`

## Acceptance criteria

- [ ] Follow toggles instantly, persists, syncs across screens
- [ ] Like double-tap shows heart animation
- [ ] Comments load paginated, newest first
- [ ] Can delete own comment, post author can delete any comment
- [ ] Save works from feed and place detail; both stay in sync
- [ ] Saved places screen lists all saves with cover photos
- [ ] Share opens native sheet with correct URL
- [ ] Private profile blocks non-followers from seeing posts

## Out of scope (v1)

- Direct messages
- Comment threads
- Reactions beyond heart
- Multiple saved collections
- Stories / ephemeral content
- Activity feed beyond a simple list of in-app notifications
- Push notifications (in-app only; push in v2 with Expo Notifications)
