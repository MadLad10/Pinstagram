import { api } from "./client";

export interface FeedPost {
  id: string;
  media_url: string;
  media_type: "image" | "video";
  thumbnail_url: string | null;
  caption: string | null;
  hashtags: string[] | null;
  price_mentioned: number | null;
  rating: number | null;
  status: string;
  like_count: number;
  comment_count: number;
  is_liked_by_me: boolean;
  is_saved_by_me: boolean;
  author: { id: string; name: string; avatar_url: string | null; is_verified: boolean };
  place: { id: string; name: string; category: string; area: string | null; district: string | null; avg_rating: number };
  created_at: string;
}

export interface PaginatedPosts {
  items: FeedPost[];
  next_cursor: string | null;
}

export const feedApi = {
  getFeed: (cursor?: string, lat?: number, lng?: number) =>
    api.get<PaginatedPosts>("/feed", { params: { cursor, lat, lng, limit: 20 } }).then((r) => r.data),

  getTrending: (cursor?: string) =>
    api.get<PaginatedPosts>("/feed/trending", { params: { cursor, limit: 20 } }).then((r) => r.data),

  likePost: (postId: string) => api.post(`/posts/${postId}/like`),
  unlikePost: (postId: string) => api.delete(`/posts/${postId}/like`),
};
