import { Ionicons } from "@expo/vector-icons";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { useEffect } from "react";
import { ActivityIndicator, FlatList, Pressable, RefreshControl, Text, View } from "react-native";
import { Notification, notificationsApi } from "../lib/api/notifications";
import { timeAgo } from "../lib/time";

function describe(n: Notification): string {
  const who = n.actor?.name ?? "Someone";
  switch (n.type) {
    case "like":
      return `${who} liked your post`;
    case "comment":
      return `${who} commented: ${n.message ?? ""}`;
    case "follow":
      return `${who} started following you`;
    case "post_approved":
      return "Your post was approved and is now live";
    case "post_rejected":
      return `Your post was not approved${n.message ? `: ${n.message}` : ""}`;
    case "review_approved":
      return "Your review was published";
  }
}

export default function NotificationsScreen() {
  const router = useRouter();
  const qc = useQueryClient();
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, refetch, isRefetching } = useInfiniteQuery({
    queryKey: ["notifications"],
    queryFn: ({ pageParam }) => notificationsApi.list(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  // Opening the screen marks everything read; the unread dots stay for this visit.
  useEffect(() => {
    notificationsApi.markAllRead().then(() => qc.invalidateQueries({ queryKey: ["notifications", "unread"] }));
  }, [qc]);

  const items = data?.pages.flatMap((p) => p.items) ?? [];

  const open = (n: Notification) => {
    if (n.type === "follow" && n.actor) router.push(`/profile/${n.actor.id}`);
    else if (n.place_id) router.push(`/place/${n.place_id}`);
  };

  return (
    <View className="flex-1 bg-white">
      <View className="flex-row items-center px-4 pt-12 pb-3 border-b border-gray-100">
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <Ionicons name="arrow-back" size={22} color="#111827" />
        </Pressable>
        <Text className="text-lg font-bold ml-3">Notifications</Text>
      </View>
      {isLoading ? (
        <ActivityIndicator color="#E91E63" style={{ marginTop: 32 }} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(n) => n.id}
          refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#E91E63" />}
          onEndReached={() => hasNextPage && !isFetchingNextPage && fetchNextPage()}
          renderItem={({ item }) => (
            <Pressable className="flex-row items-center px-4 py-3 border-b border-gray-50" onPress={() => open(item)}>
              <View className="w-10 h-10 rounded-full bg-gray-200 mr-3 overflow-hidden items-center justify-center">
                {item.actor?.avatar_url ? (
                  <Image source={{ uri: item.actor.avatar_url }} style={{ width: "100%", height: "100%" }} />
                ) : (
                  <Ionicons name={item.type.startsWith("post") || item.type.startsWith("review") ? "shield-checkmark" : "person"} size={18} color="#9CA3AF" />
                )}
              </View>
              <Text className="flex-1 text-sm" numberOfLines={2}>
                {describe(item)}
              </Text>
              <Text className="text-xs text-gray-400 ml-2">{timeAgo(item.created_at)}</Text>
              {!item.is_read && <View className="w-2 h-2 rounded-full bg-pink-600 ml-2" />}
            </Pressable>
          )}
          ListEmptyComponent={
            <View className="items-center py-20">
              <Ionicons name="notifications-off-outline" size={36} color="#9CA3AF" />
              <Text className="text-gray-400 mt-2">No notifications yet</Text>
            </View>
          }
        />
      )}
    </View>
  );
}
