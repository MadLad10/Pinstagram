import { useInfiniteQuery } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ActivityIndicator, FlatList, Pressable, Text, View } from "react-native";
import FollowButton from "../../../components/social/FollowButton";
import { socialApi, UserProfile } from "../../../lib/api/social";
import { useAuthStore } from "../../../store/auth";

export default function FollowersScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const currentUser = useAuthStore((s) => s.user);

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } = useInfiniteQuery({
    queryKey: ["followers", id],
    queryFn: ({ pageParam }) => socialApi.getFollowers(id, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page: any) => page.next_cursor ?? undefined,
  });

  const users: UserProfile[] = data?.pages.flatMap((p: any) => p.items) ?? [];

  return (
    <View className="flex-1 bg-white">
      <FlatList
        data={users}
        keyExtractor={(u) => u.id}
        ListHeaderComponent={() => (
          <View className="px-4 pt-12 pb-4 border-b border-gray-100">
            <Pressable onPress={() => router.back()} className="mb-4">
              <Text className="text-gray-400">← Back</Text>
            </Pressable>
            <Text className="text-xl font-bold">Followers</Text>
          </View>
        )}
        renderItem={({ item }) => (
          <Pressable
            className="flex-row items-center px-4 py-3 border-b border-gray-50"
            onPress={() => router.push(`/profile/${item.id}`)}
          >
            {item.avatar_url ? (
              <Image
                source={{ uri: item.avatar_url }}
                className="w-11 h-11 rounded-full"
                contentFit="cover"
              />
            ) : (
              <View className="w-11 h-11 rounded-full bg-gray-200" />
            )}
            <View className="flex-1 ml-3">
              <Text className="font-semibold">{item.name}</Text>
              {item.bio && (
                <Text className="text-xs text-gray-400 mt-0.5" numberOfLines={1}>
                  {item.bio}
                </Text>
              )}
            </View>
            {currentUser?.id !== item.id && (
              <FollowButton userId={item.id} isFollowing={item.is_following} />
            )}
          </Pressable>
        )}
        onEndReached={() => { if (hasNextPage) fetchNextPage(); }}
        onEndReachedThreshold={0.5}
        ListFooterComponent={isFetchingNextPage ? <ActivityIndicator color="#E91E63" className="py-4" /> : null}
        ListEmptyComponent={
          isLoading
            ? <ActivityIndicator color="#E91E63" className="mt-12" />
            : (
              <View className="items-center py-12">
                <Text className="text-gray-400">No followers yet</Text>
              </View>
            )
        }
      />
    </View>
  );
}
