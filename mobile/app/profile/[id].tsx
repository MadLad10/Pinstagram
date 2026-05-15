import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ActivityIndicator, FlatList, Pressable, Text, View } from "react-native";
import FollowButton from "../../components/social/FollowButton";
import { api } from "../../lib/api/client";
import { socialApi } from "../../lib/api/social";
import { useAuthStore } from "../../store/auth";

interface Post {
  id: string;
  media_url: string;
  caption: string | null;
}

export default function PublicProfileScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const currentUser = useAuthStore((s) => s.user);

  const { data: profile, isLoading } = useQuery({
    queryKey: ["profile", id],
    queryFn: () => socialApi.getProfile(id),
  });

  const { data: postsData, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
    queryKey: ["profile-posts", id],
    queryFn: ({ pageParam }) =>
      api.get(`/users/${id}/posts`, { params: { cursor: pageParam, limit: 18 } }).then((r) => r.data),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page: any) => page.next_cursor ?? undefined,
  });

  const posts: Post[] = postsData?.pages.flatMap((p: any) => p.items) ?? [];
  const isOwnProfile = currentUser?.id === id;

  if (isLoading) {
    return (
      <View className="flex-1 bg-white items-center justify-center">
        <ActivityIndicator color="#E91E63" />
      </View>
    );
  }

  if (!profile) return null;

  return (
    <View className="flex-1 bg-white">
      <FlatList
        data={posts}
        keyExtractor={(p) => p.id}
        numColumns={3}
        ListHeaderComponent={() => (
          <View>
            <View className="px-4 pt-12 pb-4">
              <Pressable onPress={() => router.back()} className="mb-4">
                <Text className="text-gray-400">← Back</Text>
              </Pressable>

              <View className="items-center mb-4">
                {profile.avatar_url ? (
                  <Image
                    source={{ uri: profile.avatar_url }}
                    className="w-24 h-24 rounded-full"
                    contentFit="cover"
                  />
                ) : (
                  <View className="w-24 h-24 rounded-full bg-gray-200" />
                )}
                <Text className="text-xl font-bold mt-3">{profile.name}</Text>
                {profile.bio && (
                  <Text className="text-gray-500 text-center mt-1 text-sm">{profile.bio}</Text>
                )}
                {profile.location && (
                  <Text className="text-gray-400 text-xs mt-1">{profile.location}</Text>
                )}
              </View>

              <View className="flex-row justify-around mb-4 border-y border-gray-100 py-4">
                <Pressable
                  className="items-center"
                  onPress={() => router.push(`/profile/${id}/followers`)}
                >
                  <Text className="text-lg font-bold">{profile.follower_count}</Text>
                  <Text className="text-xs text-gray-500">Followers</Text>
                </Pressable>
                <Pressable
                  className="items-center"
                  onPress={() => router.push(`/profile/${id}/following`)}
                >
                  <Text className="text-lg font-bold">{profile.following_count}</Text>
                  <Text className="text-xs text-gray-500">Following</Text>
                </Pressable>
                <View className="items-center">
                  <Text className="text-lg font-bold">{profile.post_count}</Text>
                  <Text className="text-xs text-gray-500">Posts</Text>
                </View>
              </View>

              {!isOwnProfile && (
                <View className="items-center mb-4">
                  <FollowButton userId={id} isFollowing={profile.is_following} />
                </View>
              )}
            </View>
          </View>
        )}
        renderItem={({ item }) => (
          <View className="flex-1 m-px aspect-square">
            <Image
              source={{ uri: item.media_url }}
              className="flex-1"
              contentFit="cover"
            />
          </View>
        )}
        onEndReached={() => { if (hasNextPage) fetchNextPage(); }}
        onEndReachedThreshold={0.5}
        ListFooterComponent={isFetchingNextPage ? <ActivityIndicator color="#E91E63" className="py-4" /> : null}
        ListEmptyComponent={
          <View className="items-center py-12">
            <Text className="text-gray-400">No posts yet</Text>
          </View>
        }
      />
    </View>
  );
}
