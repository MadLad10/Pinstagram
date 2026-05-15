import { useInfiniteQuery } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ActivityIndicator, FlatList, Pressable, Text, View } from "react-native";
import ReviewCard from "../../../components/reviews/ReviewCard";
import { reviewsApi } from "../../../lib/api/reviews";

export default function AllReviewsScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } = useInfiniteQuery({
    queryKey: ["reviews", id],
    queryFn: ({ pageParam }) => reviewsApi.list(id, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });

  const reviews = data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <View className="flex-1 bg-white">
      <FlatList
        data={reviews}
        keyExtractor={(r) => r.id}
        ListHeaderComponent={() => (
          <View className="px-4 pt-12 pb-4 border-b border-gray-100">
            <Pressable onPress={() => router.back()} className="mb-4">
              <Text className="text-gray-400">← Back</Text>
            </Pressable>
            <Text className="text-xl font-bold">All Reviews</Text>
          </View>
        )}
        renderItem={({ item }) => (
          <View className="px-4">
            <ReviewCard review={item} />
          </View>
        )}
        onEndReached={() => { if (hasNextPage) fetchNextPage(); }}
        onEndReachedThreshold={0.5}
        ListFooterComponent={
          isFetchingNextPage
            ? <ActivityIndicator color="#E91E63" className="py-4" />
            : null
        }
        ListEmptyComponent={
          isLoading
            ? <ActivityIndicator color="#E91E63" className="mt-12" />
            : (
              <View className="items-center py-12">
                <Text className="text-gray-400">No reviews yet</Text>
              </View>
            )
        }
      />

      <View className="px-4 pb-8 pt-2 border-t border-gray-100">
        <Pressable
          className="bg-pink-600 rounded-xl py-4 items-center"
          onPress={() => router.push(`/place/${id}/review`)}
        >
          <Text className="text-white font-semibold">Write a Review</Text>
        </Pressable>
      </View>
    </View>
  );
}
