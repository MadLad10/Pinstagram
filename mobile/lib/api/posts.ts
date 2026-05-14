import { api } from "./client";

export const postsApi = {
  presign: (filename: string, content_type: string, size: number) =>
    api.post<{ upload_url: string; file_key: string; expires_at: string }>("/uploads/presign", { filename, content_type, size }).then((r) => r.data),

  create: (data: {
    place_id: string;
    file_key: string;
    media_type: string;
    caption?: string;
    hashtags?: string[];
    price_mentioned?: number;
    rating?: number;
  }) => api.post("/posts", data).then((r) => r.data),

  delete: (id: string) => api.delete(`/posts/${id}`),

  getComments: (postId: string, cursor?: string) =>
    api.get(`/posts/${postId}/comments`, { params: { cursor, limit: 20 } }).then((r) => r.data),

  addComment: (postId: string, body: string) =>
    api.post(`/posts/${postId}/comments`, { body }).then((r) => r.data),

  deleteComment: (postId: string, commentId: string) =>
    api.delete(`/posts/${postId}/comments/${commentId}`),
};
