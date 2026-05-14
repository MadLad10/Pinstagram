# PROJECT.md

## What we're building

A Bangladesh-focused mobile app that combines four ideas into one:
- **Instagram** — aesthetic photos/videos of places
- **Google Maps** — find locations, get directions
- **TripAdvisor** — reviews and ratings
- **Rome2Rio** — transport options with real costs

The differentiator is **practical transport info for Bangladesh**: bus routes, fares, ride-hail estimates, train options. No other discovery app in the country covers this.

## Target users

- People aged 18–35 in Bangladesh
- Food lovers, casual travelers, content creators
- Anyone asking "where should I go this weekend" or "how do I even get there"

## User roles

| Role | Highlights |
|---|---|
| Regular User | Browse, post, save, review. 5 posts/day. |
| Premium User (৳99/mo) | Ad-free, offline maps, unlimited posts, advanced filters |
| Business Owner | Claim listing, respond to reviews, see analytics, paid verified badge |
| Content Creator | Verified status, monetization, analytics |
| Admin | Moderation, verification, transport data, bans |

## MVP scope (v1)

Build only these for the first release:

1. **Auth** — email + Google login, JWT
2. **User profiles** — basic info, follow/unfollow
3. **Visual feed** — scrollable photos/videos
4. **Place details page** — info, photos, reviews, ratings
5. **"How to Get There"** — the killer feature (bus, ride-hail, walking, train)
6. **Posting** — upload photo/video tagged to a place, with moderation queue
7. **Reviews & ratings** — write and read reviews
8. **Save places** — bookmark to "Saved" list
9. **Search** — by name, area, category
10. **Map view** — places as pins on a map

## Deferred to v2+

- Premium subscription billing
- Booking (hotels, restaurant tables)
- Cost calculator
- Multi-stop route planner
- Offline maps
- Business owner dashboard
- Influencer monetization
- Collections beyond a single "Saved" list
- Real-time notifications (start with pull-to-refresh; push later)

Don't build v2 features in v1, even if they seem easy. Ship v1 first.

## Non-goals

- Not a Booking.com clone (booking is v2 and optional)
- Not a full social network (no DMs in v1)
- Not international — Bangladesh only

## Success criteria for v1

A user in Dhaka can:
1. Sign up
2. Open the app and see a feed of real places
3. Tap a cafe in Banani
4. See photos, rating, address, and a clear "from your location, take bus X for ৳40, ~30 min, OR Uber for ~৳200, ~18 min"
5. Save it, post their own photo when they visit, write a review

If that loop works smoothly, v1 ships.
