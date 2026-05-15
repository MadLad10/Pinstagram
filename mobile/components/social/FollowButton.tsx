import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Pressable, Text } from "react-native";
import { socialApi } from "../../lib/api/social";

interface Props {
  userId: string;
  isFollowing: boolean;
}

export default function FollowButton({ userId, isFollowing }: Props) {
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => isFollowing ? socialApi.unfollow(userId) : socialApi.follow(userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profile", userId] }),
  });

  return (
    <Pressable
      className={`px-5 py-2 rounded-full border ${isFollowing ? "border-gray-300 bg-white" : "bg-pink-600 border-pink-600"}`}
      onPress={() => mutation.mutate()}
      disabled={mutation.isPending}
    >
      {mutation.isPending
        ? <ActivityIndicator size="small" color={isFollowing ? "#374151" : "white"} />
        : <Text className={`font-semibold text-sm ${isFollowing ? "text-gray-700" : "text-white"}`}>
            {isFollowing ? "Following" : "Follow"}
          </Text>
      }
    </Pressable>
  );
}
