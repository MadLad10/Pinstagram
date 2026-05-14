import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { authApi } from "../../lib/api/auth";
import { useAuthStore } from "../../store/auth";

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const login = useAuthStore((s) => s.login);

  const handleLogin = async () => {
    if (!email.trim() || !password) return;
    setLoading(true);
    try {
      const res = await authApi.login(email.trim(), password);
      await login(res.access_token, res.refresh_token, res.user);
    } catch (e: any) {
      Alert.alert("Login failed", e?.response?.data?.detail ?? "Invalid email or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View className="flex-1 bg-white justify-center px-6">
      <Text className="text-3xl font-bold text-center mb-2 text-pink-600">Pinstagram</Text>
      <Text className="text-gray-500 text-center mb-8">Discover Bangladesh</Text>

      <TextInput
        className="border border-gray-300 rounded-xl px-4 py-3 mb-4 text-base"
        placeholder="Email"
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
      />
      <TextInput
        className="border border-gray-300 rounded-xl px-4 py-3 mb-6 text-base"
        placeholder="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />

      <Pressable
        className="bg-pink-600 rounded-xl py-4 items-center mb-4"
        onPress={handleLogin}
        disabled={loading}
      >
        {loading ? <ActivityIndicator color="white" /> : <Text className="text-white font-semibold text-base">Log in</Text>}
      </Pressable>

      <Pressable onPress={() => router.push("/(auth)/signup")}>
        <Text className="text-center text-gray-500">
          Don't have an account? <Text className="text-pink-600 font-medium">Sign up</Text>
        </Text>
      </Pressable>
    </View>
  );
}
