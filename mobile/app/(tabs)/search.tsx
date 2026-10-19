import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Image } from "expo-image";
import { ActivityIndicator, Platform, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { aiApi, HybridFilters } from "../../lib/api/ai";
import { searchApi } from "../../lib/api/search";
import { useDebounce } from "../../lib/hooks/useDebounce";

// Natural-language place search ("quiet cafe with wifi") is web-only for now.
const HYBRID = Platform.OS === "web";
const PRICE_LABELS: Record<string, string> = { budget: "৳", mid: "৳৳", luxury: "৳৳৳" };
const FILTERS: { key: keyof HybridFilters; options: [string, string][] }[] = [
  {
    key: "category",
    options: [
      ["restaurant", "Restaurants"], ["cafe", "Cafes"], ["hotel", "Hotels"],
      ["historical", "Historical"], ["scenic", "Scenic"], ["aesthetic", "Aesthetic"],
    ],
  },
  { key: "price_tier", options: [["budget", "৳ Budget"], ["mid", "৳৳ Mid"], ["luxury", "৳৳৳ Luxury"]] },
  {
    key: "area",
    options: ["Dhanmondi", "Gulshan", "Banani", "Mirpur", "Uttara", "Karwan Bazar", "Nazira Bazar"].map((a) => [a, a]),
  },
];

function FilterChips({ value, onChange }: { value: HybridFilters; onChange: (f: HybridFilters) => void }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} className="mt-3" contentContainerStyle={{ gap: 6 }}>
      {FILTERS.flatMap(({ key, options }, i) => [
        ...(i > 0 ? [<View key={`sep-${key}`} className="w-px bg-gray-200 mx-1" />] : []),
        ...options.map(([v, label]) => {
          const on = value[key] === v;
          return (
            <Pressable
              key={`${key}-${v}`}
              onPress={() => onChange({ ...value, [key]: on ? undefined : v })}
              className={`px-3 py-1.5 rounded-full border ${on ? "bg-pink-600 border-pink-600" : "bg-white border-gray-200"}`}
            >
              <Text className={`text-sm ${on ? "text-white" : "text-gray-600"}`}>{label}</Text>
            </Pressable>
          );
        }),
      ])}
    </ScrollView>
  );
}

export default function SearchScreen() {
  const [q, setQ] = useState("");
  const debouncedQ = useDebounce(q, 250);
  const router = useRouter();
  const [filters, setFilters] = useState<HybridFilters>({});

  const { data, isLoading } = useQuery({
    queryKey: ["search", debouncedQ],
    queryFn: () => searchApi.search(debouncedQ),
    enabled: debouncedQ.length >= 2,
  });

  const hybrid = useQuery({
    queryKey: ["search-hybrid", debouncedQ, filters],
    queryFn: () => aiApi.hybridSearch(debouncedQ, filters),
    enabled: HYBRID && debouncedQ.length >= 2,
    placeholderData: (prev) => prev,
  });
  const places: any[] = (HYBRID ? hybrid.data?.items : data?.places) ?? [];
  const loading = isLoading || (HYBRID && hybrid.isLoading);

  return (
    <View className="flex-1 bg-white">
      <View className="px-4 pt-12 pb-3">
        <TextInput
          className="bg-gray-100 rounded-xl px-4 py-3 text-base"
          placeholder={HYBRID ? "Try \"quiet cafe with wifi\" or \"cheap biryani\"" : "Search places, people, hashtags..."}
          value={q}
          onChangeText={setQ}
          autoCapitalize="none"
        />
        {HYBRID && debouncedQ.length >= 2 && <FilterChips value={filters} onChange={setFilters} />}
      </View>

      {loading && <ActivityIndicator color="#E91E63" style={{ marginTop: 16 }} />}

      <ScrollView className="flex-1 px-4">
        {places.length > 0 && (
          <View className="mb-4">
            <Text className="font-semibold text-gray-700 mb-2">Places</Text>
            {places.map((p) => (
              <Pressable key={p.id} className="py-3 border-b border-gray-100" onPress={() => router.push(`/place/${p.id}`)}>
                <Text className="font-medium">{p.name}</Text>
                <Text className="text-sm text-gray-500 capitalize">
                  {p.category} · {p.area} · ★ {Number(p.avg_rating).toFixed(1)}
                  {HYBRID && p.price_tier ? ` · ${PRICE_LABELS[p.price_tier]}` : ""}
                </Text>
                {p.match?.review_snippet && (
                  <Text className="text-sm text-gray-600 italic mt-1" numberOfLines={2}>
                    “{p.match.review_snippet}”
                  </Text>
                )}
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

        {debouncedQ.length >= 2 && !loading && !places.length && !data?.users?.length && !data?.posts?.length && (
          <Text className="text-gray-400 text-center mt-8">No results for "{debouncedQ}"</Text>
        )}
      </ScrollView>
    </View>
  );
}
