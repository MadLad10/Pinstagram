import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import StarRating from "../../../components/reviews/StarRating";
import { reviewsApi } from "../../../lib/api/reviews";

export default function WriteReviewScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [rating, setRating] = useState(0);
  const [body, setBody] = useState("");
  const [price, setPrice] = useState("");

  const mutation = useMutation({
    mutationFn: () => reviewsApi.create(id, {
      rating,
      body,
      price_paid: price ? parseInt(price) : undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["place", id] });
      Alert.alert("Review submitted", "It'll appear once approved.");
      router.back();
    },
    onError: (e: any) => {
      Alert.alert("Error", e?.response?.data?.detail ?? "Something went wrong");
    },
  });

  const canSubmit = rating > 0 && body.length >= 50 && !mutation.isPending;

  return (
    <ScrollView className="flex-1 bg-white">
      <View className="px-4 pt-12 pb-8">
        <Pressable onPress={() => router.back()} className="mb-6">
          <Text className="text-gray-400">← Back</Text>
        </Pressable>
        <Text className="text-xl font-bold mb-6">Write a Review</Text>

        <Text className="font-medium mb-3">Your rating</Text>
        <StarRating value={rating} onChange={setRating} size={36} />

        <Text className="font-medium mt-6 mb-2">Your review</Text>
        <TextInput
          className="border border-gray-200 rounded-xl px-4 py-3 text-sm min-h-[120px]"
          placeholder="Share your experience (min 50 characters)..."
          value={body}
          onChangeText={setBody}
          multiline
          textAlignVertical="top"
        />
        <Text className={`text-xs mt-1 ${body.length < 50 ? "text-gray-400" : "text-green-500"}`}>
          {body.length}/50 min
        </Text>

        <Text className="font-medium mt-6 mb-2">Price paid (optional)</Text>
        <TextInput
          className="border border-gray-200 rounded-xl px-4 py-3 text-sm"
          placeholder="৳ Amount"
          value={price}
          onChangeText={setPrice}
          keyboardType="number-pad"
        />

        <Pressable
          className={`mt-8 rounded-xl py-4 items-center ${canSubmit ? "bg-pink-600" : "bg-gray-200"}`}
          onPress={() => mutation.mutate()}
          disabled={!canSubmit}
        >
          {mutation.isPending
            ? <ActivityIndicator color="white" />
            : <Text className={`font-semibold ${canSubmit ? "text-white" : "text-gray-400"}`}>Submit Review</Text>
          }
        </Pressable>
      </View>
    </ScrollView>
  );
}
