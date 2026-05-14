# search-and-map.md — Search & Map View

## Search

### Entry
- Search bar in top of home, dedicated search tab, and place picker in compose

### Endpoint
```
GET /search?q=<query>&type=<all|places|posts|users|hashtags>&cursor=
```

### Behavior
- Min 2 chars before query fires
- Debounce 250ms on frontend
- Returns 4 sections when `type=all`:
  - **Places** (top 5) — matches on name, area, district
  - **Hashtags** (top 5) — matches starting with query
  - **Users** (top 3) — matches on name
  - **Posts** (top 10) — matches on caption + hashtags
- Tabs at top of results screen let user filter to one section

### Place search ranking
1. Exact name match
2. Name starts-with match
3. Name contains match
4. Area / district match
5. Boost by `avg_rating` and `review_count`

### Recent searches
- Store last 10 in SecureStore (frontend only, not synced to backend)
- Show as chips when search bar is empty
- "Clear all" button

## Map View

### Entry
- Bottom tab "Map"
- Also accessible from search results ("Show on map")

### Behavior
- Full-screen Google Map
- User's location (blue dot) if GPS granted
- Pins for places visible in current viewport
- Pins color-coded by category:
  - 🔴 Hotel
  - 🟠 Restaurant
  - 🟡 Cafe
  - 🟢 Scenic
  - 🟣 Historical
  - 🔵 Aesthetic

### Pin loading
- On map move/zoom: debounce 500ms, then `GET /places?near_lat&near_lng&radius_m` based on viewport
- Max 50 pins at once; cluster beyond that (use Google Maps clustering)

### Pin interaction
- Tap pin → bottom sheet with mini-card (photo, name, rating, "View details" button)
- Tap mini-card → place detail screen

### Filters
- Floating filter button → bottom sheet
  - Category multi-select
  - Min rating
  - Price tier
- Filters apply to the place query

### "Near me" button
- Re-centers to user location, sets radius to 5km

## Files to create

**Backend**
- `app/api/v1/search.py`
- `app/services/search_service.py` — uses Postgres full-text search (`tsvector`) for v1
- Migration: add `tsvector` column to `places`, `posts`, GIN indexes

**Frontend**
- `app/(tabs)/search.tsx`
- `app/(tabs)/map.tsx`
- `components/search/SearchBar.tsx`
- `components/search/SearchResults.tsx`
- `components/map/MapPin.tsx`
- `components/map/PlaceBottomSheet.tsx`
- `components/map/FilterSheet.tsx`
- `lib/api/search.ts`
- `lib/hooks/useSearch.ts` — debounced TanStack query

## Search backend tech

v1: Postgres full-text search with `tsvector`. Simple and free.
v2: Move to Elasticsearch / Meilisearch if needed.

```sql
ALTER TABLE places ADD COLUMN search_vector tsvector
  GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(area, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(district, '')), 'C')
  ) STORED;

CREATE INDEX places_search_idx ON places USING GIN(search_vector);
```

Query with `search_vector @@ plainto_tsquery('english', :q)` ordered by `ts_rank`.

## Acceptance criteria

### Search
- [ ] Returns results within 500ms for typical queries
- [ ] Debounce prevents request spam
- [ ] Recent searches persist across app restarts
- [ ] Empty state for no results
- [ ] Tabbed filtering works

### Map
- [ ] Renders user location when permission granted
- [ ] Pins load on pan/zoom without lag
- [ ] Clustering works beyond 50 pins
- [ ] Tapping a pin opens the bottom sheet smoothly
- [ ] Filters update pins immediately
- [ ] "Near me" recenters correctly

## Out of scope (v1)

- Bangla-language search (use English only for v1 since most place names are in English; v2 add Bangla)
- Voice search
- Image search ("find places that look like this")
- Saved searches with alerts
