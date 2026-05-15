import { api } from "./client";

export interface Review {
  id: string;
  user_id: string;
  place_id: string;
  rating: number;
  body: string;
  price_paid: number | null;
  status: string;
  created_at: string;
  updated_at: string;
  author_name: string | null;
  author_avatar_url: string | null;
}

export const reviewsApi = {
  list: (placeId: string, cursor?: string) =>
    api.get<{ items: Review[]; next_cursor: string | null }>(`/places/${placeId}/reviews`, { params: { cursor, limit: 20 } }).then((r) => r.data),

  create: (placeId: string, data: { rating: number; body: string; price_paid?: number }) =>
    api.post<Review>(`/places/${placeId}/reviews`, data).then((r) => r.data),

  update: (reviewId: string, data: { rating?: number; body?: string; price_paid?: number }) =>
    api.patch<Review>(`/reviews/${reviewId}`, data).then((r) => r.data),

  delete: (reviewId: string) => api.delete(`/reviews/${reviewId}`),
};
