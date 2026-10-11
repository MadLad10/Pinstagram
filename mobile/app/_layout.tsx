import "../global.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Image } from "expo-image";
import { Stack, useRouter, useSegments } from "expo-router";
import { cssInterop } from "nativewind";
import { useEffect } from "react";
import { Platform, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useAuthStore } from "../store/auth";

// Let expo-image accept Tailwind classes like any core component.
cssInterop(Image, { className: "style" });

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 1000 * 60, retry: 1 } },
});

function AuthGate() {
  const { user, isHydrated, hydrate } = useAuthStore();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    hydrate();
  }, []);

  useEffect(() => {
    if (!isHydrated) return;
    const inAuth = segments[0] === "(auth)";
    // A freshly signed-up user is logged in but should still see verify-email.
    const verifying = inAuth && (segments as string[])[1] === "verify-email";
    if (!user && !inAuth) router.replace("/(auth)/login");
    if (user && inAuth && !verifying) router.replace("/(tabs)");
  }, [user, isHydrated, segments]);

  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: "#fff" } }} />;
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <QueryClientProvider client={queryClient}>
        {Platform.OS === "web" ? (
          // On desktop browsers, render the app as a centered phone-width column.
          <View style={{ flex: 1, backgroundColor: "#F3F4F6", alignItems: "center" }}>
            <View style={{ flex: 1, width: "100%", maxWidth: 480, backgroundColor: "#fff", overflow: "hidden" }}>
              <AuthGate />
            </View>
          </View>
        ) : (
          <AuthGate />
        )}
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}
