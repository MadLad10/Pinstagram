import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import * as Linking from "expo-linking";
import { useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { DirectionsOption, RideHailProvider } from "../../lib/api/directions";
import { placesApi } from "../../lib/api/places";
import { formatDuration } from "../../lib/time";

interface Props {
  placeId: string;
  userLat: number;
  userLng: number;
  placeLat: number;
  placeLng: number;
}

const ICONS: Record<DirectionsOption["mode"], string> = { bus: "🚌", ride_hail: "🚗", train: "🚆", walk: "🚶" };
const TITLES: Record<DirectionsOption["mode"], string> = { bus: "Bus", ride_hail: "Ride-hail", train: "Train", walk: "Walk" };

function openRideHail(provider: RideHailProvider["name"], lat: number, lng: number) {
  if (provider === "uber") {
    const params = `action=setPickup&pickup=my_location&dropoff[latitude]=${lat}&dropoff[longitude]=${lng}`;
    Linking.openURL(`uber://?${params}`).catch(() => Linking.openURL(`https://m.uber.com/ul/?${params}`));
    return;
  }
  // Pathao and Obhai don't publish destination deep links; open the app (or its store page).
  const urls: Record<string, [string, string]> = {
    pathao: ["pathao://", "https://pathao.com/bn/rides/"],
    obhai: ["obhai://", "https://obhai.com/"],
  };
  const [app, web] = urls[provider] ?? ["", "https://www.google.com/maps"];
  Linking.openURL(app).catch(() => Linking.openURL(web));
}

function Summary({ option }: { option: DirectionsOption }) {
  if (option.mode === "bus") {
    const ride = option.steps.find((s) => s.type === "bus");
    return <Text className="text-xs text-gray-500">{ride && ride.type === "bus" ? `${ride.route_name} · ${ride.num_stops} stops` : ""}</Text>;
  }
  if (option.mode === "ride_hail") return <Text className="text-xs text-gray-500">{option.providers.map((p) => p.name).join(", ")}</Text>;
  if (option.mode === "train")
    return <Text className="text-xs text-gray-500">{option.next_departure ? `Next: ${option.next_departure}` : "See timetable"}</Text>;
  return <Text className="text-xs text-gray-500">{(option.distance_m / 1000).toFixed(1)} km</Text>;
}

function Details({ option, placeLat, placeLng }: { option: DirectionsOption; placeLat: number; placeLng: number }) {
  if (option.mode === "ride_hail")
    return (
      <>
        {option.providers.map((p) => (
          <View key={p.name} className="flex-row items-center mt-3">
            <Text className="capitalize font-medium flex-1">{p.name}</Text>
            <Text className="text-gray-600 text-sm mr-3">৳{p.cost_low}–{p.cost_high}</Text>
            <Pressable className="bg-black rounded-lg px-3 py-1.5" onPress={() => openRideHail(p.name, placeLat, placeLng)}>
              <Text className="text-white text-xs font-medium">Open</Text>
            </Pressable>
          </View>
        ))}
        <Text className="text-xs text-gray-400 mt-3">Estimates. Surge pricing may apply.</Text>
      </>
    );
  if (option.mode === "walk")
    return (
      <Text className="text-sm text-gray-500 mt-3">
        {option.recommended ? "Close enough to walk." : "That's a long walk — consider another option."}
      </Text>
    );
  return (
    <>
      {option.steps.map((step, i) => (
        <View key={i} className="flex-row items-start gap-3 mt-3">
          <Text>{step.type === "walk" ? "🚶" : step.type === "bus" ? "🚌" : "🚆"}</Text>
          <View className="flex-1">
            <Text className="text-sm font-medium">
              {step.type === "walk"
                ? `Walk to ${step.to}`
                : step.type === "bus"
                  ? `${step.route_name}: ${step.from_stop} → ${step.to_stop}`
                  : `${step.from_station} → ${step.to_station}`}
            </Text>
            <Text className="text-xs text-gray-400">
              {formatDuration(step.duration_s)}
              {step.type === "walk" ? ` · ${step.distance_m} m` : ` · ৳${step.fare}`}
              {step.type === "bus" && step.operator ? ` · ${step.operator}` : ""}
              {step.type === "train" && step.departure_time ? ` · departs ${step.departure_time}` : ""}
            </Text>
          </View>
        </View>
      ))}
    </>
  );
}

export default function HowToGetThere({ placeId, userLat, userLng, placeLat, placeLng }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const { data, isLoading, isError, refetch } = useQuery({
    // Round the origin so small GPS jitter doesn't refetch.
    queryKey: ["directions", placeId, userLat.toFixed(3), userLng.toFixed(3)],
    queryFn: () => placesApi.getDirections(placeId, userLat, userLng),
  });

  return (
    <View className="mb-6">
      <Text className="font-semibold text-lg mb-1">How to Get There</Text>
      {data && <Text className="text-xs text-gray-400 mb-3">{(data.distance_m / 1000).toFixed(1)} km from you</Text>}

      {isLoading && <ActivityIndicator color="#E91E63" />}
      {isError && (
        <Pressable onPress={() => refetch()}>
          <Text className="text-gray-500">Couldn't load directions. <Text className="text-pink-600">Retry</Text></Text>
        </Pressable>
      )}

      {data?.options.map((option) => {
        const open = expanded === option.mode;
        return (
          <View key={option.mode} className="border border-gray-200 rounded-xl mb-3 overflow-hidden">
            <Pressable className="flex-row items-center px-4 py-3" onPress={() => setExpanded(open ? null : option.mode)}>
              <Text className="text-xl mr-3">{ICONS[option.mode]}</Text>
              <View className="flex-1">
                <View className="flex-row items-center gap-2">
                  <Text className="font-medium">{TITLES[option.mode]}</Text>
                  {option.label && (
                    <View className="bg-pink-50 px-2 py-0.5 rounded-full">
                      <Text className="text-[10px] font-semibold text-pink-600">{option.label}</Text>
                    </View>
                  )}
                </View>
                <Summary option={option} />
              </View>
              <View className="items-end mr-2">
                <Text className="font-semibold">{option.total_cost ? `৳${option.total_cost}` : "Free"}</Text>
                <Text className="text-xs text-gray-500">{formatDuration(option.total_duration_s)}</Text>
              </View>
              <Ionicons name={open ? "chevron-up" : "chevron-down"} size={16} color="#9CA3AF" />
            </Pressable>
            {open && (
              <View className="px-4 pb-4 border-t border-gray-100">
                <Details option={option} placeLat={placeLat} placeLng={placeLng} />
              </View>
            )}
          </View>
        );
      })}
    </View>
  );
}
