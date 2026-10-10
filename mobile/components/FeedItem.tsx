import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { Pressable, Text, View } from "react-native";
import { FeedPost } from "../lib/api/feed";
import { timeAgo } from "../lib/time";

interface Props {
  post: FeedPost;
  onLike: () => void;
  onComment: () => void;
  onSave: () => void;
  onPlacePress: () => void;
  onAuthorPress: () => void;
}

export default function FeedItem({ post, onLike, onComment, onSave, onPlacePress, onAuthorPress }: Props) {
  return (
    <View className="bg-white mb-2 border-b border-gray-100">
      {/* Header */}
      <View className="flex-row items-center px-4 py-3">
        <Pressable onPress={onAuthorPress} className="w-9 h-9 rounded-full bg-gray-200 mr-3 overflow-hidden">
          {post.author.avatar_url && (
            <Image source={{ uri: post.author.avatar_url }} style={{ width: "100%", height: "100%" }} />
          )}
        </Pressable>
        <View className="flex-1">
          <Pressable className="flex-row items-center gap-1" onPress={onAuthorPress}>
            <Text className="font-semibold text-sm">{post.author.name}</Text>
            {post.author.is_verified && <Ionicons name="checkmark-circle" size={14} color="#E91E63" />}
          </Pressable>
          <Pressable onPress={onPlacePress}>
            <Text className="text-xs text-pink-600">
              {post.place.name}
              {post.place.area ? ` · ${post.place.area}` : ""}
            </Text>
          </Pressable>
        </View>
        <Text className="text-xs text-gray-400">{timeAgo(post.created_at)}</Text>
      </View>

      {/* Media */}
      <Image
        source={{ uri: post.thumbnail_url ?? post.media_url }}
        style={{ width: "100%", aspectRatio: 1 }}
        contentFit="cover"
        transition={150}
      />

      {/* Actions */}
      <View className="flex-row items-center px-4 py-2 gap-4">
        <Pressable className="flex-row items-center gap-1" onPress={onLike} hitSlop={8}>
          <Ionicons
            name={post.is_liked_by_me ? "heart" : "heart-outline"}
            size={24}
            color={post.is_liked_by_me ? "#E91E63" : "#374151"}
          />
          <Text className="text-sm text-gray-600">{post.like_count}</Text>
        </Pressable>
        <Pressable className="flex-row items-center gap-1" onPress={onComment} hitSlop={8}>
          <Ionicons name="chatbubble-outline" size={22} color="#374151" />
          <Text className="text-sm text-gray-600">{post.comment_count}</Text>
        </Pressable>
        <View className="flex-1" />
        <Pressable onPress={onSave} hitSlop={8}>
          <Ionicons
            name={post.is_saved_by_me ? "bookmark" : "bookmark-outline"}
            size={22}
            color={post.is_saved_by_me ? "#E91E63" : "#374151"}
          />
        </Pressable>
      </View>

      {/* Caption */}
      {(post.caption || post.price_mentioned) && (
        <View className="px-4 pb-3">
          {post.caption && (
            <Text className="text-sm">
              <Text className="font-semibold">{post.author.name} </Text>
              {post.caption}
            </Text>
          )}
          {post.hashtags && post.hashtags.length > 0 && (
            <Text className="text-sm text-pink-600 mt-0.5">{post.hashtags.map((t) => `#${t}`).join(" ")}</Text>
          )}
          {post.price_mentioned != null && (
            <Text className="text-xs text-gray-500 mt-1">Spent ৳{post.price_mentioned}</Text>
          )}
        </View>
      )}
    </View>
  );
}
