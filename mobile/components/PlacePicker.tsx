import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native";
import { placesApi, PlaceSummary } from "../lib/api/places";
import { useDebounce } from "../lib/hooks/useDebounce";

interface Props {
  value: PlaceSummary | null;
  onChange: (place: PlaceSummary | null) => void;
}

/** Search-as-you-type place selector used to tag posts. */
export default function PlacePicker({ value, onChange }: Props) {
  const [q, setQ] = useState("");
  const debounced = useDebounce(q.trim(), 250);
  const { data, isFetching } = useQuery({
    queryKey: ["place-picker", debounced],
    queryFn: () => placesApi.list({ q: debounced, limit: 6 }),
    enabled: debounced.length >= 2 && !value,
  });

  if (value)
    return (
      <View className="flex-row items-center border border-pink-200 bg-pink-50 rounded-xl px-4 py-3 mb-3">
        <Ionicons name="location" size={18} color="#E91E63" />
        <View className="flex-1 ml-2">
          <Text className="font-medium">{value.name}</Text>
          <Text className="text-xs text-gray-500 capitalize">
            {value.category}
            {value.area ? ` · ${value.area}` : ""}
          </Text>
        </View>
        <Pressable onPress={() => onChange(null)} hitSlop={8}>
          <Ionicons name="close-circle" size={20} color="#9CA3AF" />
        </Pressable>
      </View>
    );

  return (
    <View className="mb-3">
      <View className="flex-row items-center border border-gray-200 rounded-xl px-4">
        <Ionicons name="search" size={16} color="#9CA3AF" />
        <TextInput
          className="flex-1 py-3 ml-2"
          placeholder="Tag a place (e.g. Lalbagh, cafe banani)"
          value={q}
          onChangeText={setQ}
          autoCapitalize="none"
        />
        {isFetching && <ActivityIndicator size="small" color="#E91E63" />}
      </View>
      {data?.items.map((p) => (
        <Pressable
          key={p.id}
          className="px-4 py-3 border-b border-gray-100"
          onPress={() => {
            onChange(p);
            setQ("");
          }}
        >
          <Text className="font-medium">{p.name}</Text>
          <Text className="text-xs text-gray-500 capitalize">
            {p.category}
            {p.area ? ` · ${p.area}` : ""}
          </Text>
        </Pressable>
      ))}
      {debounced.length >= 2 && data?.items.length === 0 && (
        <Text className="text-gray-400 text-sm px-4 py-3">No places match “{debounced}”</Text>
      )}
    </View>
  );
}
