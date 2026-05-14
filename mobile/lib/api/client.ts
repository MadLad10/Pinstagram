import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import * as SecureStore from "expo-secure-store";

const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const api = axios.create({ baseURL: BASE_URL });

api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const token = await SecureStore.getItemAsync("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let isRefreshing = false;
let failedQueue: Array<{ resolve: (v: unknown) => void; reject: (e: unknown) => void }> = [];

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach((p) => (error ? p.reject(error) : p.resolve(token)));
  failedQueue = [];
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status !== 401 || original._retry) return Promise.reject(error);

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      })
        .then((token) => {
          original.headers.Authorization = `Bearer ${token}`;
          return api(original);
        })
        .catch(Promise.reject);
    }

    original._retry = true;
    isRefreshing = true;

    try {
      const refreshToken = await SecureStore.getItemAsync("refresh_token");
      if (!refreshToken) throw new Error("No refresh token");
      const res = await axios.post(`${BASE_URL}/auth/refresh`, { refresh_token: refreshToken });
      const { access_token, refresh_token } = res.data;
      await SecureStore.setItemAsync("access_token", access_token);
      await SecureStore.setItemAsync("refresh_token", refresh_token);
      api.defaults.headers.common.Authorization = `Bearer ${access_token}`;
      processQueue(null, access_token);
      original.headers.Authorization = `Bearer ${access_token}`;
      return api(original);
    } catch (e) {
      processQueue(e, null);
      await SecureStore.deleteItemAsync("access_token");
      await SecureStore.deleteItemAsync("refresh_token");
      return Promise.reject(e);
    } finally {
      isRefreshing = false;
    }
  }
);
