import { useQuery } from "@tanstack/react-query";
import { Pressable, ScrollView, Text, View, ActivityIndicator } from "react-native";
import { useAuthStore } from "../../store/auth";
import { api } from "../../lib/api/client";

export default function MyProfileScreen() {
  const { user, logout } = useAuthStore();

  const { data: saved, isLoading } = useQuery({
    queryKey: ["saved-places"],
    queryFn: () => api.get("/users/me/saved-places").then((r) => r.data),
  });

  if (!user) return null;

  return (
    <ScrollView className="flex-1 bg-white">
      <View className="px-4 pt-12 pb-6 items-center border-b border-gray-100">
        <View className="w-20 h-20 rounded-full bg-gray-200 mb-3" />
        <Text className="text-xl font-bold">{user.name}</Text>
        {user.bio && <Text className="text-gray-500 text-center mt-1">{user.bio}</Text>}
        <Text className="text-gray-400 text-sm mt-1">{user.location ?? "Bangladesh"}</Text>
      </View>

      <View className="px-4 py-4 border-b border-gray-100">
        <Text className="font-semibold text-gray-700 mb-3">Saved Places</Text>
        {isLoading && <ActivityIndicator color="#E91E63" />}
        {saved?.items?.length === 0 && <Text className="text-gray-400">No saved places yet</Text>}
        {saved?.items?.map((p: any) => (
          <View key={p.id} className="py-2 border-b border-gray-50">
            <Text className="font-medium">{p.name}</Text>
            <Text className="text-xs text-gray-400 capitalize">{p.category} · {p.area}</Text>
          </View>
        ))}
      </View>

      <View className="px-4 py-6">
        <Pressable className="border border-red-300 rounded-xl py-3 items-center" onPress={logout}>
          <Text className="text-red-500 font-medium">Log out</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
