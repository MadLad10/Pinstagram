import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Image } from "expo-image";
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { searchApi } from "../../lib/api/search";
import { useDebounce } from "../../lib/hooks/useDebounce";

export default function SearchScreen() {
  const [q, setQ] = useState("");
  const debouncedQ = useDebounce(q, 250);
  const router = useRouter();

  const { data, isLoading } = useQuery({
    queryKey: ["search", debouncedQ],
    queryFn: () => searchApi.search(debouncedQ),
    enabled: debouncedQ.length >= 2,
  });

  return (
    <View className="flex-1 bg-white">
      <View className="px-4 pt-12 pb-3">
        <TextInput
          className="bg-gray-100 rounded-xl px-4 py-3 text-base"
          placeholder="Search places, people, hashtags..."
          value={q}
          onChangeText={setQ}
          autoCapitalize="none"
        />
      </View>

      {isLoading && <ActivityIndicator color="#E91E63" style={{ marginTop: 16 }} />}

      <ScrollView className="flex-1 px-4">
        {data?.places?.length > 0 && (
          <View className="mb-4">
            <Text className="font-semibold text-gray-700 mb-2">Places</Text>
            {data.places.map((p: any) => (
              <Pressable key={p.id} className="py-3 border-b border-gray-100" onPress={() => router.push(`/place/${p.id}`)}>
                <Text className="font-medium">{p.name}</Text>
                <Text className="text-sm text-gray-500 capitalize">
                  {p.category} · {p.area} · ★ {Number(p.avg_rating).toFixed(1)}
                </Text>
              </Pressable>
            ))}
          </View>
        )}

        {data?.users?.length > 0 && (
          <View className="mb-4">
            <Text className="font-semibold text-gray-700 mb-2">People</Text>
            {data.users.map((u: any) => (
              <Pressable key={u.id} className="py-3 border-b border-gray-100" onPress={() => router.push(`/profile/${u.id}`)}>
                <Text className="font-medium">{u.name}</Text>
              </Pressable>
            ))}
          </View>
        )}

        {data?.hashtags?.length > 0 && (
          <View className="mb-4">
            <Text className="font-semibold text-gray-700 mb-2">Hashtags</Text>
            <View className="flex-row flex-wrap gap-2">
              {data.hashtags.map((tag: string) => (
                <Pressable key={tag} className="bg-pink-50 px-3 py-1 rounded-full" onPress={() => setQ(`#${tag}`)}>
                  <Text className="text-pink-600 text-sm">#{tag}</Text>
                </Pressable>
              ))}
            </View>
          </View>
        )}

        {data?.posts?.length > 0 && (
          <View className="mb-4">
            <Text className="font-semibold text-gray-700 mb-2">Posts</Text>
            <View className="flex-row flex-wrap">
              {data.posts.map((p: any) => (
                <Pressable key={p.id} className="w-1/3 aspect-square p-px" onPress={() => router.push(`/place/${p.place_id}`)}>
                  <Image source={{ uri: p.thumbnail_url ?? p.media_url }} style={{ flex: 1 }} contentFit="cover" />
                </Pressable>
              ))}
            </View>
          </View>
        )}

        {debouncedQ.length >= 2 && !isLoading && !data?.places?.length && !data?.users?.length && !data?.posts?.length && (
          <Text className="text-gray-400 text-center mt-8">No results for "{debouncedQ}"</Text>
        )}
      </ScrollView>
    </View>
  );
}
