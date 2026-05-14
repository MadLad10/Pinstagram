import { api } from "./client";

export interface User {
  id: string;
  email: string;
  name: string;
  bio: string | null;
  avatar_url: string | null;
  location: string | null;
  is_private: boolean;
  is_verified: boolean;
  role: string;
  is_premium: boolean;
  email_verified: boolean;
  created_at: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
  refresh_token: string;
}

export const authApi = {
  signup: (email: string, password: string, name: string) =>
    api.post<AuthResponse>("/auth/signup", { email, password, name }).then((r) => r.data),

  login: (email: string, password: string) =>
    api.post<AuthResponse>("/auth/login", { email, password }).then((r) => r.data),

  googleAuth: (id_token: string) =>
    api.post<AuthResponse>("/auth/google", { id_token }).then((r) => r.data),

  refresh: (refresh_token: string) =>
    api.post<{ access_token: string; refresh_token: string }>("/auth/refresh", { refresh_token }).then((r) => r.data),

  logout: (refresh_token: string) =>
    api.post("/auth/logout", { refresh_token }),

  verifyEmail: (email: string, code: string) =>
    api.post<{ verified: boolean }>("/auth/verify-email", { email, code }).then((r) => r.data),

  getMe: () => api.get<User>("/users/me").then((r) => r.data),
};
