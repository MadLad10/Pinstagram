import { storage } from "../lib/storage";
import { create } from "zustand";
import { authApi, User } from "../lib/api/auth";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  isHydrated: boolean;
  login: (accessToken: string, refreshToken: string, user: User) => Promise<void>;
  logout: () => Promise<void>;
  hydrate: () => Promise<void>;
  setUser: (user: User) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  isLoading: false,
  isHydrated: false,

  login: async (accessToken, refreshToken, user) => {
    await storage.set("access_token", accessToken);
    await storage.set("refresh_token", refreshToken);
    set({ accessToken, refreshToken, user });
  },

  logout: async () => {
    const { refreshToken } = get();
    try {
      if (refreshToken) await authApi.logout(refreshToken);
    } catch {}
    await storage.remove("access_token");
    await storage.remove("refresh_token");
    set({ user: null, accessToken: null, refreshToken: null });
  },

  hydrate: async () => {
    set({ isLoading: true });
    try {
      const accessToken = await storage.get("access_token");
      const refreshToken = await storage.get("refresh_token");
      if (accessToken && refreshToken) {
        const user = await authApi.getMe();
        set({ accessToken, refreshToken, user });
      }
    } catch {
      await storage.remove("access_token");
      await storage.remove("refresh_token");
    } finally {
      set({ isLoading: false, isHydrated: true });
    }
  },

  setUser: (user) => set({ user }),
}));
