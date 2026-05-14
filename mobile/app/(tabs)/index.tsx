import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useCallback } from "react";
import { ActivityIndicator, FlatList, RefreshControl, Text, View } from "react-native";
import FeedItem from "../../components/FeedItem";
import { feedApi, FeedPost } from "../../lib/api/feed";

export default function FeedScreen() {
  const router = useRouter();
  const qc = useQueryClient();

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError, refetch, isRefetching } =
    useInfiniteQuery({
      queryKey: ["feed"],
      queryFn: ({ pageParam }) => feedApi.getFeed(pageParam as string | undefined),
      initialPageParam: undefined as string | undefined,
      getNextPageParam: (last) => last.next_cursor ?? undefined,
    });

  const posts = data?.pages.flatMap((p) => p.items) ?? [];

  const likeMutation = useMutation({
    mutationFn: ({ id, liked }: { id: string; liked: boolean }) =>
      liked ? feedApi.unlikePost(id) : feedApi.likePost(id),
    onMutate: async ({ id, liked }) => {
      await qc.cancelQueries({ queryKey: ["feed"] });
      const prev = qc.getQueryData(["feed"]);
      qc.setQueryData(["feed"], (old: any) => ({
        ...old,
        pages: old.pages.map((page: any) => ({
          ...page,
          items: page.items.map((p: FeedPost) =>
            p.id === id
              ? { ...p, is_liked_by_me: !liked, like_count: p.like_count + (liked ? -1 : 1) }
              : p
          ),
        })),
      }));
      return { prev };
    },
    onError: (_e, _v, ctx) => qc.setQueryData(["feed"], ctx?.prev),
  });

  const renderItem = useCallback(
    ({ item }: { item: FeedPost }) => (
      <FeedItem
        post={item}
        onLike={() => likeMutation.mutate({ id: item.id, liked: item.is_liked_by_me })}
        onPlacePress={() => router.push(`/place/${item.place.id}`)}
        onAuthorPress={() => router.push(`/profile/${item.author.id}`)}
      />
    ),
    [likeMutation, router]
  );

  if (isLoading) return <View className="flex-1 items-center justify-center"><ActivityIndicator size="large" color="#E91E63" /></View>;

  if (isError && posts.length === 0)
    return (
      <View className="flex-1 items-center justify-center px-8">
        <Text className="text-gray-500 text-center mb-4">Could not load feed</Text>
        <Text className="text-pink-600 font-medium" onPress={() => refetch()}>Retry</Text>
      </View>
    );

  return (
    <FlatList
      data={posts}
      keyExtractor={(item) => item.id}
      renderItem={renderItem}
      onEndReached={() => hasNextPage && !isFetchingNextPage && fetchNextPage()}
      onEndReachedThreshold={0.3}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#E91E63" />}
      ListEmptyComponent={
        <View className="flex-1 items-center justify-center py-20">
          <Text className="text-gray-400 text-center">No posts yet — follow some people or explore the map!</Text>
        </View>
      }
      ListFooterComponent={isFetchingNextPage ? <ActivityIndicator size="small" color="#E91E63" className="py-4" /> : null}
    />
  );
}
