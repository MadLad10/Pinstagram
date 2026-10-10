import { api } from "./client";

export interface Notification {
  id: string;
  type: "like" | "comment" | "follow" | "post_approved" | "post_rejected" | "review_approved";
  actor: { id: string; name: string; avatar_url: string | null; is_verified: boolean } | null;
  post_id: string | null;
  place_id: string | null;
  message: string | null;
  is_read: boolean;
  created_at: string;
}

export interface PaginatedNotifications {
  items: Notification[];
  next_cursor: string | null;
  unread_count: number;
}

export const notificationsApi = {
  list: (cursor?: string) =>
    api.get<PaginatedNotifications>("/notifications", { params: { cursor, limit: 20 } }).then((r) => r.data),

  markAllRead: () => api.post("/notifications/read-all"),
};
