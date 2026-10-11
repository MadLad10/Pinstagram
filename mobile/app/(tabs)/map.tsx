import { keepPreviousData, useQuery } from "@tanstack/react-query";
import * as Location from "expo-location";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import PlacesMap from "../../components/map/PlacesMap";
import { MapRegion } from "../../components/map/types";
import { placesApi, PlaceSummary } from "../../lib/api/places";
import { useDebounce } from "../../lib/hooks/useDebounce";

const CATEGORY_COLORS: Record<string, string> = {
  hotel: "#EF4444",
  restaurant: "#F97316",
  cafe: "#EAB308",
  scenic: "#22C55E",
  historical: "#A855F7",
  aesthetic: "#3B82F6",
};

const DHAKA: MapRegion = { latitude: 23.7806, longitude: 90.4074, latitudeDelta: 0.12, longitudeDelta: 0.12 };

export default function MapScreen() {
  const router = useRouter();
  const [region, setRegion] = useState<MapRegion>(DHAKA);
  const [recenterKey, setRecenterKey] = useState(0);
  const [category, setCategory] = useState<string | null>(null);
  const [selected, setSelected] = useState<PlaceSummary | null>(null);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  // Wait for panning to settle before refetching pins.
  const settled = useDebounce(region, 300);

  useEffect(() => {
    Location.requestForegroundPermissionsAsync().then(({ status }) => {
      if (status === "granted") {
        Location.getCurrentPositionAsync({}).then((loc) =>
          setUserLocation({ lat: loc.coords.latitude, lng: loc.coords.longitude })
        );
      }
    });
  }, []);

  // Radius that covers the visible map (half the diagonal), in meters.
  const radiusM = Math.round(
    Math.min(Math.max((Math.hypot(settled.latitudeDelta, settled.longitudeDelta) / 2) * 111_000, 1000), 100_000)
  );
  const { data } = useQuery({
    queryKey: ["map-places", settled.latitude.toFixed(3), settled.longitude.toFixed(3), radiusM, category],
    queryFn: () =>
      placesApi.list({
        near_lat: settled.latitude,
        near_lng: settled.longitude,
        radius_m: radiusM,
        category: category ?? undefined,
        limit: 100,
      }),
    placeholderData: keepPreviousData,
  });

  return (
    <View className="flex-1">
      <PlacesMap
        initialRegion={DHAKA}
        places={data?.items.filter((p) => p.lat != null && p.lng != null) ?? []}
        colors={CATEGORY_COLORS}
        userLocation={userLocation}
        recenterKey={recenterKey}
        onRegionChange={setRegion}
        onSelect={setSelected}
      />

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        className="absolute top-12 left-0 right-0"
        style={{ zIndex: 1000 }}
        contentContainerStyle={{ paddingHorizontal: 12, gap: 8 }}
      >
        {[null, ...Object.keys(CATEGORY_COLORS)].map((c) => (
          <Pressable
            key={c ?? "all"}
            onPress={() => setCategory(c)}
            className={`px-4 py-2 rounded-full shadow ${category === c ? "bg-pink-600" : "bg-white"}`}
          >
            <Text className={`capitalize text-sm font-medium ${category === c ? "text-white" : "text-gray-700"}`}>
              {c ?? "All"}
            </Text>
          </Pressable>
        ))}
      </ScrollView>

      {userLocation && (
        <Pressable
          className="absolute bottom-40 right-4 bg-white rounded-full p-3 shadow-md"
          style={{ zIndex: 1000 }}
          onPress={() => setRecenterKey((k) => k + 1)}
        >
          <Text className="text-lg">📍</Text>
        </Pressable>
      )}

      {selected && (
        <View className="absolute bottom-0 left-0 right-0 bg-white p-4 rounded-t-2xl shadow-lg" style={{ zIndex: 1000 }}>
          <Text className="font-bold text-lg">{selected.name}</Text>
          <Text className="text-gray-500 capitalize">
            {selected.category}
            {selected.area ? ` · ${selected.area}` : ""}
          </Text>
          <Text className="text-yellow-500 mt-1">★ {selected.avg_rating.toFixed(1)}</Text>
          <Pressable className="bg-pink-600 rounded-xl py-3 mt-3 items-center" onPress={() => router.push(`/place/${selected.id}`)}>
            <Text className="text-white font-semibold">View details & directions</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}
