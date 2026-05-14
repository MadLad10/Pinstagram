import * as SecureStore from "expo-secure-store";
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
    await SecureStore.setItemAsync("access_token", accessToken);
    await SecureStore.setItemAsync("refresh_token", refreshToken);
    set({ accessToken, refreshToken, user });
  },

  logout: async () => {
    const { refreshToken } = get();
    try {
      if (refreshToken) await authApi.logout(refreshToken);
    } catch {}
    await SecureStore.deleteItemAsync("access_token");
    await SecureStore.deleteItemAsync("refresh_token");
    set({ user: null, accessToken: null, refreshToken: null });
  },

  hydrate: async () => {
    set({ isLoading: true });
    try {
      const accessToken = await SecureStore.getItemAsync("access_token");
      const refreshToken = await SecureStore.getItemAsync("refresh_token");
      if (accessToken && refreshToken) {
        const user = await authApi.getMe();
        set({ accessToken, refreshToken, user });
      }
    } catch {
      await SecureStore.deleteItemAsync("access_token");
      await SecureStore.deleteItemAsync("refresh_token");
    } finally {
      set({ isLoading: false, isHydrated: true });
    }
  },

  setUser: (user) => set({ user }),
}));
