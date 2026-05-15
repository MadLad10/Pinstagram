import { Text, View } from "react-native";
import { Review } from "../../lib/api/reviews";
import StarRating from "./StarRating";

interface Props {
  review: Review;
}

export default function ReviewCard({ review }: Props) {
  return (
    <View className="py-4 border-b border-gray-100">
      <View className="flex-row items-center gap-3 mb-2">
        <View className="w-9 h-9 rounded-full bg-gray-200" />
        <View className="flex-1">
          <Text className="font-semibold text-sm">{review.author_name ?? "User"}</Text>
          <Text className="text-xs text-gray-400">{new Date(review.created_at).toLocaleDateString()}</Text>
        </View>
        <StarRating value={review.rating} size={14} />
      </View>
      <Text className="text-gray-700 text-sm leading-relaxed">{review.body}</Text>
      {review.price_paid != null && (
        <Text className="text-xs text-gray-400 mt-1">Paid ৳{review.price_paid}</Text>
      )}
    </View>
  );
}
