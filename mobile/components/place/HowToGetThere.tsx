import { useQuery } from "@tanstack/react-query";
import * as Linking from "expo-linking";
import { useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { placesApi } from "../../lib/api/places";

interface Props {
  placeId: string;
  userLat: number;
  userLng: number;
  placeLat: number | null;
  placeLng: number | null;
}

export default function HowToGetThere({ placeId, userLat, userLng, placeLat, placeLng }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["directions", placeId, userLat.toFixed(4), userLng.toFixed(4)],
    queryFn: () => placesApi.getDirections(placeId, userLat, userLng),
    enabled: !!placeLat && !!placeLng,
  });

  const openUber = () => {
    if (!placeLat || !placeLng) return;
    Linking.openURL(`uber://?action=setPickup&pickup=my_location&dropoff[latitude]=${placeLat}&dropoff[longitude]=${placeLng}`).catch(() =>
      Linking.openURL(`https://m.uber.com/ul/?action=setPickup&pickup=my_location&dropoff[latitude]=${placeLat}&dropoff[longitude]=${placeLng}`)
    );
  };

  const openPathao = () => {
    Linking.openURL("https://pathao.com").catch(() => {});
  };

  return (
    <View className="mb-6">
      <Text className="font-semibold text-lg mb-3">How to Get There</Text>

      {isLoading && <ActivityIndicator color="#E91E63" />}

      {data?.options?.map((option: any) => (
        <View key={option.mode} className="border border-gray-200 rounded-xl mb-3 overflow-hidden">
          <Pressable
            className="flex-row items-center px-4 py-3"
            onPress={() => setExpanded(expanded === option.mode ? null : option.mode)}
          >
            <Text className="text-xl mr-3">
              {option.mode === "bus" ? "🚌" : option.mode === "ride_hail" ? "🚗" : option.mode === "train" ? "🚂" : "🚶"}
            </Text>
            <View className="flex-1">
              <Text className="font-medium capitalize">{option.mode.replace("_", " ")}</Text>
              {option.label && <Text className="text-xs text-gray-400">{option.label}</Text>}
            </View>
            {option.total_cost != null && (
              <Text className="text-pink-600 font-semibold">৳{option.total_cost}</Text>
            )}
            {option.mode === "walk" && (
              <Text className="text-gray-500 text-sm">{Math.round(option.duration_s / 60)} min</Text>
            )}
            <Ionicons name={expanded === option.mode ? "chevron-up" : "chevron-down"} size={16} color="#9CA3AF" className="ml-2" />
          </Pressable>

          {expanded === option.mode && (
            <View className="px-4 pb-4 border-t border-gray-100">
              {/* Bus steps */}
              {option.mode === "bus" && option.steps?.map((step: any, i: number) => (
                <View key={i} className="flex-row items-start gap-2 mt-2">
                  <Text>{step.type === "walk" ? "🚶" : "🚌"}</Text>
                  <View>
                    <Text className="text-sm font-medium">
                      {step.type === "walk" ? `Walk to ${step.to}` : `${step.route_name}: ${step.from_stop} → ${step.to_stop}`}
                    </Text>
                    <Text className="text-xs text-gray-400">
                      {Math.round(step.duration_s / 60)} min{step.fare ? ` · ৳${step.fare}` : ""}
                    </Text>
                  </View>
                </View>
              ))}

              {/* Ride-hail providers */}
              {option.mode === "ride_hail" && option.providers?.map((p: any) => (
                <View key={p.name} className="flex-row items-center mt-2">
                  <Text className="capitalize font-medium flex-1">{p.name}</Text>
                  <Text className="text-gray-600 text-sm mr-3">৳{p.cost_low}–{p.cost_high} · {Math.round(p.duration_s / 60)} min</Text>
                  <Pressable className="bg-black rounded-lg px-3 py-1" onPress={p.name === "uber" ? openUber : openPathao}>
                    <Text className="text-white text-xs font-medium">Open</Text>
                  </Pressable>
                </View>
              ))}

              {/* Train */}
              {option.mode === "train" && (
                <View className="mt-2">
                  <Text className="text-sm">{option.from_station} → {option.to_station}</Text>
                  <Text className="text-xs text-gray-400">৳{option.fare} · {Math.round(option.duration_s / 60)} min</Text>
                </View>
              )}

              {/* Walk */}
              {option.mode === "walk" && (
                <Text className="text-sm text-gray-500 mt-2">
                  {option.recommended ? "Walking is a good option from here." : "Walk is long — consider another option."}
                </Text>
              )}
            </View>
          )}
        </View>
      ))}
    </View>
  );
}
