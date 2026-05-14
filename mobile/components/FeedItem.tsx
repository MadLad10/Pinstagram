import { Image, Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { FeedPost } from "../lib/api/feed";

interface Props {
  post: FeedPost;
  onLike: () => void;
  onPlacePress: () => void;
  onAuthorPress: () => void;
}

export default function FeedItem({ post, onLike, onPlacePress, onAuthorPress }: Props) {
  return (
    <View className="bg-white mb-2 border-b border-gray-100">
      {/* Header */}
      <Pressable className="flex-row items-center px-4 py-3" onPress={onAuthorPress}>
        <View className="w-9 h-9 rounded-full bg-gray-200 mr-3 overflow-hidden">
          {post.author.avatar_url && (
            <Image source={{ uri: post.author.avatar_url }} className="w-full h-full" />
          )}
        </View>
        <View className="flex-1">
          <Text className="font-semibold text-sm">{post.author.name}</Text>
          <Pressable onPress={onPlacePress}>
            <Text className="text-xs text-pink-600">{post.place.name} · {post.place.area}</Text>
          </Pressable>
        </View>
        {post.author.is_verified && <Ionicons name="checkmark-circle" size={16} color="#E91E63" />}
      </Pressable>

      {/* Media */}
      <Image
        source={{ uri: post.media_url }}
        className="w-full aspect-square"
        resizeMode="cover"
      />

      {/* Actions */}
      <View className="flex-row items-center px-4 py-2 gap-4">
        <Pressable className="flex-row items-center gap-1" onPress={onLike}>
          <Ionicons name={post.is_liked_by_me ? "heart" : "heart-outline"} size={24} color={post.is_liked_by_me ? "#E91E63" : "#374151"} />
          <Text className="text-sm text-gray-600">{post.like_count}</Text>
        </Pressable>
        <Pressable className="flex-row items-center gap-1">
          <Ionicons name="chatbubble-outline" size={22} color="#374151" />
          <Text className="text-sm text-gray-600">{post.comment_count}</Text>
        </Pressable>
        <View className="flex-1" />
        <Ionicons name={post.is_saved_by_me ? "bookmark" : "bookmark-outline"} size={22} color="#374151" />
      </View>

      {/* Caption */}
      {post.caption && (
        <View className="px-4 pb-3">
          <Text className="text-sm">
            <Text className="font-semibold">{post.author.name} </Text>
            {post.caption}
          </Text>
          {post.price_mentioned && (
            <Text className="text-xs text-gray-400 mt-1">৳{post.price_mentioned}</Text>
          )}
        </View>
      )}
    </View>
  );
}
