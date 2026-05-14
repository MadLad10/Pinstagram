# place-details.md — Place Details Page

## What this covers

The detail screen for a single place (hotel, restaurant, cafe, scenic spot, etc.). The page where users land after tapping a feed item, map pin, or search result.

## Sections (top to bottom)

1. **Hero gallery** — cover photo + swipeable photos/videos from posts
2. **Header** — name, category icon, verified badge, avg rating + review count
3. **Action bar** — Save, Share, Write Review, Get Directions
4. **Key info** — address (tap to copy), phone (tap to call), website link, opening hours, price tier (৳/৳৳/৳৳৳)
5. **"How to Get There"** — see the dedicated section below
6. **Amenities chips** — parking, AC, wifi, outdoor seating, etc.
7. **Social proof** — "X people saved this", "Y posted photos this month"
8. **Recent posts** — horizontal scroll of recent user posts tagged here
9. **Reviews** — top 3 reviews + "See all" button
10. **Nearby places** — 4–6 similar/nearby places (same category, within 2km)

## API

```
GET /places/{place_id}?from_lat=&from_lng=
```

If `from_lat`/`from_lng` provided, the response includes a `directions_preview` with the cheapest and fastest options inline. Otherwise client calls `/directions` separately.

## How to Get There (the differentiator)

See ARCHITECTURE.md for the algorithm. UI requirements:

- Renders as **cards stacked vertically** — Bus, Ride-hail, Train, Walking
- Each card shows: mode icon, **label** ("Cheapest" / "Fastest" / etc.), cost in ৳, duration, and a "See steps" expander
- Bus card expanded: numbered walking + bus steps
- Ride-hail card: provider rows with cost ranges and "Book in Uber" / "Book in Pathao" deep links
- If user hasn't granted GPS: show a "Set your starting location" button → opens a location picker
- If no bus route found: hide the bus card (don't show empty state — just omit)
- Always show at least ride-hail (always available)

### Deep links for ride-hail

- Uber: `uber://?action=setPickup&pickup=my_location&dropoff[latitude]={lat}&dropoff[longitude]={lng}`
- Pathao: open in their app if installed, else play store
- Always fall back to a regular maps deep link

## Actions

- **Save** → `POST /places/{id}/save` (optimistic, toggle bookmark icon)
- **Share** → native share sheet with deep link `bdvisual://place/{id}` and web fallback
- **Write Review** → opens review composer (see reviews feature)
- **Call** → `tel:` link
- **Directions** → opens "How to Get There" full screen if condensed on detail page
- **Report** → in overflow menu

## Caching

TanStack Query: stale time 5 minutes, cache time 1 hour. Refetch on focus only if stale.

## Files to create

**Backend**
- `app/api/v1/places.py` (place detail endpoint, save/unsave)
- `app/api/v1/directions.py` (the directions endpoint)
- `app/services/places_service.py`
- `app/services/directions_service.py` — bus, train, ride-hail, walking calculators
- `app/services/google_maps_client.py` — wrapper for Google Directions API
- `app/schemas/place.py`, `app/schemas/directions.py`

**Frontend**
- `app/place/[id].tsx`
- `components/place/HeroGallery.tsx`
- `components/place/HowToGetThere.tsx`
- `components/place/TransportCard.tsx`
- `components/place/AmenityChips.tsx`
- `components/place/ReviewList.tsx`
- `lib/api/places.ts`
- `lib/hooks/usePlace.ts`
- `lib/deeplinks.ts` — Uber/Pathao/Maps URL builders

## Acceptance criteria

- [ ] Place page loads in under 1 second on a warm cache
- [ ] All sections render with skeleton loaders while loading
- [ ] Address copy-to-clipboard works
- [ ] Phone tap opens dialer
- [ ] At least 2 transport options always shown when GPS available
- [ ] Save is optimistic, persists across app restarts
- [ ] Uber and Pathao deep links open correctly (test on real device)
- [ ] Image gallery swipeable with pinch-to-zoom
- [ ] Videos play inline in gallery
- [ ] Reviews respect moderation (`status=published` only)

## Out of scope (v1)

- Booking from the page (v2)
- Menu display for restaurants (just photos for now)
- 360° photos
- AR features
- Save to specific collection (just one "Saved" list in v1)
