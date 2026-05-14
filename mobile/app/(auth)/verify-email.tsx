import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { authApi } from "../../lib/api/auth";
import { useAuthStore } from "../../store/auth";

export default function VerifyEmailScreen() {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { user, setUser } = useAuthStore();

  const handleVerify = async () => {
    if (!user) return;
    setLoading(true);
    try {
      await authApi.verifyEmail(user.email, code);
      setUser({ ...user, email_verified: true });
      router.replace("/(tabs)");
    } catch (e: any) {
      Alert.alert("Verification failed", e?.response?.data?.detail ?? "Invalid or expired code");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View className="flex-1 bg-white justify-center px-6">
      <Text className="text-2xl font-bold text-center mb-2">Verify your email</Text>
      <Text className="text-gray-500 text-center mb-8">
        We sent a 6-digit code to {user?.email}
      </Text>

      <TextInput
        className="border border-gray-300 rounded-xl px-4 py-3 mb-6 text-center text-2xl tracking-widest"
        placeholder="000000"
        value={code}
        onChangeText={setCode}
        keyboardType="number-pad"
        maxLength={6}
      />

      <Pressable
        className="bg-pink-600 rounded-xl py-4 items-center mb-4"
        onPress={handleVerify}
        disabled={loading || code.length < 6}
      >
        {loading ? <ActivityIndicator color="white" /> : <Text className="text-white font-semibold text-base">Verify</Text>}
      </Pressable>

      <Pressable onPress={() => router.replace("/(tabs)")}>
        <Text className="text-center text-gray-400">Skip for now</Text>
      </Pressable>
    </View>
  );
}
