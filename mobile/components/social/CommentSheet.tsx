import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { ActivityIndicator, FlatList, KeyboardAvoidingView, Platform, Pressable, Text, TextInput, View } from "react-native";
import { postsApi } from "../../lib/api/posts";
import { useAuthStore } from "../../store/auth";

interface Props {
  postId: string;
  onClose: () => void;
}

export default function CommentSheet({ postId, onClose }: Props) {
  const [body, setBody] = useState("");
  const inputRef = useRef<TextInput>(null);
  const user = useAuthStore((s) => s.user);
  const qc = useQueryClient();

  const { data, fetchNextPage, hasNextPage, isLoading } = useInfiniteQuery({
    queryKey: ["comments", postId],
    queryFn: ({ pageParam }) => postsApi.getComments(postId, pageParam as string | undefined),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last: any) => last.next_cursor ?? undefined,
  });

  const comments = data?.pages.flatMap((p: any) => p.items) ?? [];

  const addMutation = useMutation({
    mutationFn: () => postsApi.addComment(postId, body.trim()),
    onSuccess: () => {
      setBody("");
      qc.invalidateQueries({ queryKey: ["comments", postId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (commentId: string) => postsApi.deleteComment(postId, commentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["comments", postId] }),
  });

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} className="flex-1">
      <View className="flex-row items-center justify-between px-4 py-3 border-b border-gray-100">
        <Text className="font-semibold text-base">Comments</Text>
        <Pressable onPress={onClose}><Text className="text-gray-400">Close</Text></Pressable>
      </View>

      {isLoading
        ? <ActivityIndicator color="#E91E63" className="mt-6" />
        : <FlatList
            data={comments}
            keyExtractor={(item: any) => item.id}
            onEndReached={() => hasNextPage && fetchNextPage()}
            onEndReachedThreshold={0.3}
            renderItem={({ item }: { item: any }) => (
              <View className="flex-row items-start px-4 py-3 border-b border-gray-50">
                <View className="w-8 h-8 rounded-full bg-gray-200 mr-3" />
                <View className="flex-1">
                  <Text className="font-semibold text-sm">{item.author?.name ?? "User"}</Text>
                  <Text className="text-sm text-gray-700 mt-0.5">{item.body}</Text>
                </View>
                {(item.user_id === user?.id) && (
                  <Pressable onPress={() => deleteMutation.mutate(item.id)}>
                    <Text className="text-gray-300 text-xs">✕</Text>
                  </Pressable>
                )}
              </View>
            )}
            ListEmptyComponent={<Text className="text-gray-400 text-center mt-8">No comments yet</Text>}
          />
      }

      <View className="flex-row items-center px-4 py-3 border-t border-gray-100 gap-3">
        <TextInput
          ref={inputRef}
          className="flex-1 bg-gray-100 rounded-xl px-4 py-2 text-sm"
          placeholder="Add a comment..."
          value={body}
          onChangeText={setBody}
          multiline
        />
        <Pressable
          className={`px-4 py-2 rounded-xl ${body.trim() ? "bg-pink-600" : "bg-gray-200"}`}
          onPress={() => body.trim() && addMutation.mutate()}
          disabled={!body.trim() || addMutation.isPending}
        >
          {addMutation.isPending
            ? <ActivityIndicator size="small" color="white" />
            : <Text className={body.trim() ? "text-white font-medium text-sm" : "text-gray-400 text-sm"}>Post</Text>
          }
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}
