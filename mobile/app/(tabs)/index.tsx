import { Ionicons } from "@expo/vector-icons";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, Modal, Pressable, RefreshControl, Text, View } from "react-native";
import FeedItem from "../../components/FeedItem";
import FeedSkeleton from "../../components/FeedSkeleton";
import CommentSheet from "../../components/social/CommentSheet";
import { feedApi, FeedPost } from "../../lib/api/feed";
import { notificationsApi } from "../../lib/api/notifications";
import { usePostActions } from "../../lib/hooks/usePostActions";

const FEED_KEY = ["feed"];

export default function FeedScreen() {
  const router = useRouter();
  const [commentsFor, setCommentsFor] = useState<string | null>(null);
  const { like, save } = usePostActions(FEED_KEY);

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError, refetch, isRefetching } =
    useInfiniteQuery({
      queryKey: FEED_KEY,
      queryFn: ({ pageParam }) => feedApi.getFeed(pageParam),
      initialPageParam: undefined as string | undefined,
      getNextPageParam: (last) => last.next_cursor ?? undefined,
    });

  const { data: unread } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => notificationsApi.list().then((r) => r.unread_count),
    refetchInterval: 60_000,
  });

  const posts = data?.pages.flatMap((p) => p.items) ?? [];

  const renderItem = useCallback(
    ({ item }: { item: FeedPost }) => (
      <FeedItem
        post={item}
        onLike={() => like(item)}
        onSave={() => save(item)}
        onComment={() => setCommentsFor(item.id)}
        onPlacePress={() => router.push(`/place/${item.place.id}`)}
        onAuthorPress={() => router.push(`/profile/${item.author.id}`)}
      />
    ),
    [like, save, router]
  );

  const header = (
    <View className="flex-row items-center justify-between px-4 pt-12 pb-3 bg-white border-b border-gray-100">
      <Text className="text-2xl font-bold text-pink-600">Pinstagram</Text>
      <Pressable onPress={() => router.push("/notifications")} hitSlop={10}>
        <Ionicons name="notifications-outline" size={24} color="#111827" />
        {!!unread && (
          <View className="absolute -top-1 -right-1 bg-pink-600 rounded-full min-w-[16px] h-4 items-center justify-center px-1">
            <Text className="text-white text-[10px] font-bold">{unread > 9 ? "9+" : unread}</Text>
          </View>
        )}
      </Pressable>
    </View>
  );

  if (isLoading)
    return (
      <View className="flex-1 bg-white">
        {header}
        <FeedSkeleton />
      </View>
    );

  if (isError && posts.length === 0)
    return (
      <View className="flex-1 bg-white">
        {header}
        <View className="flex-1 items-center justify-center px-8">
          <Ionicons name="cloud-offline-outline" size={40} color="#9CA3AF" />
          <Text className="text-gray-500 text-center my-4">Could not load your feed</Text>
          <Pressable className="bg-pink-600 rounded-xl px-6 py-2" onPress={() => refetch()}>
            <Text className="text-white font-medium">Retry</Text>
          </Pressable>
        </View>
      </View>
    );

  return (
    <View className="flex-1 bg-gray-50">
      {header}
      <FlatList
        data={posts}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        onEndReached={() => hasNextPage && !isFetchingNextPage && fetchNextPage()}
        onEndReachedThreshold={0.4}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#E91E63" />}
        ListEmptyComponent={
          <View className="items-center justify-center py-20 px-8">
            <Ionicons name="images-outline" size={40} color="#9CA3AF" />
            <Text className="text-gray-500 text-center mt-3">
              Nothing here yet. Follow people or explore the map to fill your feed.
            </Text>
          </View>
        }
        ListFooterComponent={isFetchingNextPage ? <ActivityIndicator color="#E91E63" style={{ padding: 16 }} /> : null}
      />

      <Modal visible={!!commentsFor} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setCommentsFor(null)}>
        {commentsFor && <CommentSheet postId={commentsFor} onClose={() => setCommentsFor(null)} />}
      </Modal>
    </View>
  );
}
