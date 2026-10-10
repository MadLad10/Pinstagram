import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, FlatList, Pressable, Text, View } from "react-native";
import { api } from "../../lib/api/client";
import { feedApi, FeedPost } from "../../lib/api/feed";
import { PlaceSummary } from "../../lib/api/places";
import { socialApi } from "../../lib/api/social";
import { useAuthStore } from "../../store/auth";

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
  pending: { label: "In review", className: "bg-yellow-400" },
  rejected: { label: "Rejected", className: "bg-red-500" },
};

export default function MyProfileScreen() {
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const [tab, setTab] = useState<"posts" | "saved">("posts");

  const { data: profile } = useQuery({
    queryKey: ["profile", user?.id],
    queryFn: () => socialApi.getProfile(user!.id),
    enabled: !!user,
  });

  const posts = useInfiniteQuery({
    queryKey: ["my-posts"],
    queryFn: ({ pageParam }) => feedApi.getUserPosts(user!.id, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: !!user,
  });

  const saved = useQuery({
    queryKey: ["saved-places"],
    queryFn: () => api.get<{ items: PlaceSummary[] }>("/users/me/saved-places", { params: { limit: 50 } }).then((r) => r.data),
    enabled: tab === "saved",
  });

  if (!user) return null;
  const myPosts: FeedPost[] = posts.data?.pages.flatMap((p) => p.items) ?? [];

  const header = (
    <View>
      <View className="px-4 pt-14 pb-4 items-center">
        <View className="w-20 h-20 rounded-full bg-gray-200 mb-3 overflow-hidden">
          {user.avatar_url && <Image source={{ uri: user.avatar_url }} style={{ width: "100%", height: "100%" }} />}
        </View>
        <Text className="text-xl font-bold">{user.name}</Text>
        {user.bio && <Text className="text-gray-500 text-center mt-1">{user.bio}</Text>}
        {!user.email_verified && (
          <Pressable onPress={() => router.push("/(auth)/verify-email")} className="mt-2 bg-yellow-50 px-3 py-1 rounded-full">
            <Text className="text-yellow-700 text-xs">Verify your email</Text>
          </Pressable>
        )}
      </View>

      <View className="flex-row justify-around py-3 border-y border-gray-100">
        <Stat value={profile?.post_count} label="Posts" />
        <Stat value={profile?.follower_count} label="Followers" onPress={() => router.push(`/profile/${user.id}/followers`)} />
        <Stat value={profile?.following_count} label="Following" onPress={() => router.push(`/profile/${user.id}/following`)} />
      </View>

      <View className="flex-row">
        {(["posts", "saved"] as const).map((t) => (
          <Pressable key={t} onPress={() => setTab(t)} className={`flex-1 py-3 items-center border-b-2 ${tab === t ? "border-pink-600" : "border-transparent"}`}>
            <Text className={`font-medium capitalize ${tab === t ? "text-pink-600" : "text-gray-500"}`}>{t}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );

  const footer = (
    <View className="px-4 py-8">
      <Pressable
        className="border border-red-300 rounded-xl py-3 items-center"
        onPress={() => Alert.alert("Log out?", undefined, [{ text: "Cancel" }, { text: "Log out", style: "destructive", onPress: logout }])}
      >
        <Text className="text-red-500 font-medium">Log out</Text>
      </Pressable>
    </View>
  );

  if (tab === "saved")
    return (
      <FlatList
        className="flex-1 bg-white"
        data={saved.data?.items ?? []}
        keyExtractor={(p) => p.id}
        ListHeaderComponent={header}
        ListFooterComponent={footer}
        renderItem={({ item }) => (
          <Pressable className="flex-row items-center px-4 py-3 border-b border-gray-50" onPress={() => router.push(`/place/${item.id}`)}>
            <Image source={{ uri: item.cover_photo_url ?? undefined }} style={{ width: 48, height: 48, borderRadius: 8, backgroundColor: "#E5E7EB" }} />
            <View className="ml-3 flex-1">
              <Text className="font-medium">{item.name}</Text>
              <Text className="text-xs text-gray-400 capitalize">
                {item.category} · {item.area}
              </Text>
            </View>
            <Text className="text-yellow-500 text-sm">★ {item.avg_rating.toFixed(1)}</Text>
          </Pressable>
        )}
        ListEmptyComponent={
          saved.isLoading ? <ActivityIndicator color="#E91E63" style={{ marginTop: 24 }} /> : <Text className="text-gray-400 text-center mt-8">No saved places yet</Text>
        }
      />
    );

  return (
    <FlatList
      className="flex-1 bg-white"
      data={myPosts}
      keyExtractor={(p) => p.id}
      numColumns={3}
      ListHeaderComponent={header}
      ListFooterComponent={footer}
      onEndReached={() => posts.hasNextPage && posts.fetchNextPage()}
      renderItem={({ item }) => (
        <Pressable className="flex-1 m-px aspect-square max-w-[33.3%]" onPress={() => router.push(`/place/${item.place.id}`)}>
          <Image source={{ uri: item.thumbnail_url ?? item.media_url }} style={{ flex: 1 }} contentFit="cover" />
          {STATUS_BADGE[item.status] && (
            <View className={`absolute top-1 left-1 px-1.5 py-0.5 rounded ${STATUS_BADGE[item.status].className}`}>
              <Text className="text-white text-[10px] font-semibold">{STATUS_BADGE[item.status].label}</Text>
            </View>
          )}
        </Pressable>
      )}
      ListEmptyComponent={
        posts.isLoading ? <ActivityIndicator color="#E91E63" style={{ marginTop: 24 }} /> : <Text className="text-gray-400 text-center mt-8">Share your first place from the + tab</Text>
      }
    />
  );
}

function Stat({ value, label, onPress }: { value?: number; label: string; onPress?: () => void }) {
  return (
    <Pressable className="items-center" onPress={onPress} disabled={!onPress}>
      <Text className="text-lg font-bold">{value ?? "–"}</Text>
      <Text className="text-xs text-gray-500">{label}</Text>
    </Pressable>
  );
}
