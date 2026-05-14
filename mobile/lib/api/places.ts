import { api } from "./client";

export interface Place {
  id: string;
  name: string;
  category: string;
  description: string | null;
  address: string;
  division: string | null;
  district: string | null;
  area: string | null;
  lat: number | null;
  lng: number | null;
  phone: string | null;
  website: string | null;
  price_tier: string | null;
  opening_hours: Record<string, string> | null;
  amenities: string[] | null;
  cover_photo_url: string | null;
  is_verified: boolean;
  avg_rating: number;
  review_count: number;
  save_count: number;
  is_saved_by_me: boolean;
  created_at: string;
}

export interface PlaceSummary {
  id: string;
  name: string;
  category: string;
  cover_photo_url: string | null;
  avg_rating: number;
  price_tier: string | null;
  area: string | null;
  district: string | null;
  is_verified: boolean;
  distance_m: number | null;
}

export const placesApi = {
  list: (params?: Record<string, unknown>) =>
    api.get<{ items: PlaceSummary[]; next_cursor: string | null }>("/places", { params }).then((r) => r.data),

  get: (id: string) => api.get<Place>(`/places/${id}`).then((r) => r.data),

  save: (id: string) => api.post(`/places/${id}/save`),
  unsave: (id: string) => api.delete(`/places/${id}/save`),

  getDirections: (id: string, fromLat: number, fromLng: number) =>
    api.get(`/places/${id}/directions`, { params: { from_lat: fromLat, from_lng: fromLng } }).then((r) => r.data),
};
