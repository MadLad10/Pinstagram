import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { authApi } from "../../lib/api/auth";
import { useAuthStore } from "../../store/auth";

export default function SignupScreen() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const login = useAuthStore((s) => s.login);

  const handleSignup = async () => {
    if (password.length < 8) {
      Alert.alert("Password too short", "Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      const res = await authApi.signup(email.trim(), password, name.trim());
      await login(res.access_token, res.refresh_token, res.user);
      if (!res.user.email_verified) router.replace("/(auth)/verify-email");
    } catch (e: any) {
      Alert.alert("Sign up failed", e?.response?.data?.detail ?? "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View className="flex-1 bg-white justify-center px-6">
      <Text className="text-3xl font-bold text-center mb-2 text-pink-600">Create account</Text>
      <Text className="text-gray-500 text-center mb-8">Join Pinstagram</Text>

      <TextInput
        className="border border-gray-300 rounded-xl px-4 py-3 mb-4 text-base"
        placeholder="Name"
        value={name}
        onChangeText={setName}
      />
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
        placeholder="Password (min 8 chars)"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />

      <Pressable
        className="bg-pink-600 rounded-xl py-4 items-center mb-4"
        onPress={handleSignup}
        disabled={loading}
      >
        {loading ? <ActivityIndicator color="white" /> : <Text className="text-white font-semibold text-base">Sign up</Text>}
      </Pressable>

      <Pressable onPress={() => router.back()}>
        <Text className="text-center text-gray-500">
          Already have an account? <Text className="text-pink-600 font-medium">Log in</Text>
        </Text>
      </Pressable>
    </View>
  );
}
