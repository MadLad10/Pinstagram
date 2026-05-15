import { api } from "./client";

export interface UserProfile {
  id: string;
  name: string;
  bio: string | null;
  avatar_url: string | null;
  location: string | null;
  is_private: boolean;
  is_verified: boolean;
  role: string;
  follower_count: number;
  following_count: number;
  post_count: number;
  is_following: boolean;
  is_blocked: boolean;
  created_at: string;
}

export const socialApi = {
  getProfile: (userId: string) => api.get<UserProfile>(`/users/${userId}`).then((r) => r.data),

  follow: (userId: string) => api.post(`/users/${userId}/follow`),
  unfollow: (userId: string) => api.delete(`/users/${userId}/follow`),

  block: (userId: string) => api.post(`/users/${userId}/block`),
  unblock: (userId: string) => api.delete(`/users/${userId}/block`),

  getFollowers: (userId: string, cursor?: string) =>
    api.get(`/users/${userId}/followers`, { params: { cursor, limit: 20 } }).then((r) => r.data),

  getFollowing: (userId: string, cursor?: string) =>
    api.get(`/users/${userId}/following`, { params: { cursor, limit: 20 } }).then((r) => r.data),

  report: (targetType: string, targetId: string, reason: string, notes?: string) =>
    api.post("/reports", { target_type: targetType, target_id: targetId, reason, notes }),

  updateMe: (data: { name?: string; bio?: string; avatar_url?: string; location?: string; is_private?: boolean }) =>
    api.patch("/users/me", data).then((r) => r.data),
};
