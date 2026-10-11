import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

/**
 * Token storage: the OS keychain on iOS/Android, localStorage on the web
 * (SecureStore has no web implementation).
 */
export const storage = {
  get: (key: string): Promise<string | null> =>
    Platform.OS === "web" ? Promise.resolve(localStorage.getItem(key)) : SecureStore.getItemAsync(key),

  set: (key: string, value: string): Promise<void> =>
    Platform.OS === "web" ? Promise.resolve(localStorage.setItem(key, value)) : SecureStore.setItemAsync(key, value),

  remove: (key: string): Promise<void> =>
    Platform.OS === "web" ? Promise.resolve(localStorage.removeItem(key)) : SecureStore.deleteItemAsync(key),
};
