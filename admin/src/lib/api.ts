import axios from "axios";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const client = axios.create({ baseURL: `${BASE}/api/v1` });

client.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("admin_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("admin_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export const adminApi = {
  login: (email: string, password: string) =>
    client.post("/auth/login", { email, password }).then((r) => r.data),

  stats: () =>
    client.get("/admin/stats").then((r) => r.data),

  pendingReviews: (cursor?: string) =>
    client.get("/admin/reviews/pending", { params: { cursor, limit: 20 } }).then((r) => r.data),

  approveReview: (id: string) =>
    client.post(`/admin/reviews/${id}/approve`),

  rejectReview: (id: string, reason: string) =>
    client.post(`/admin/reviews/${id}/reject`, { reason }),

  reports: (cursor?: string) =>
    client.get("/admin/reports", { params: { cursor, limit: 20 } }).then((r) => r.data),

  resolveReport: (id: string, action: string, notes?: string) =>
    client.post(`/admin/reports/${id}/resolve`, { action, notes }),

  users: (cursor?: string, search?: string) =>
    client.get("/admin/users", { params: { cursor, limit: 20, search } }).then((r) => r.data),

  banUser: (id: string, reason: string) =>
    client.post(`/admin/users/${id}/ban`, { reason }),

  unbanUser: (id: string) =>
    client.post(`/admin/users/${id}/unban`),

  promoteAdmin: (id: string) =>
    client.post(`/admin/users/${id}/promote`),

  places: (cursor?: string) =>
    client.get("/admin/places", { params: { cursor, limit: 20 } }).then((r) => r.data),

  featurePlace: (id: string) =>
    client.post(`/admin/places/${id}/feature`),

  unfeaturePlace: (id: string) =>
    client.post(`/admin/places/${id}/unfeature`),

  pendingPosts: (cursor?: string) =>
    client.get("/admin/posts/pending", { params: { cursor, limit: 20 } }).then((r) => r.data),

  approvePost: (id: string) =>
    client.post(`/admin/posts/${id}/approve`),

  rejectPost: (id: string, reason: string) =>
    client.post(`/admin/posts/${id}/reject`, { reason }),
};
