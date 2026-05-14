import { useQuery } from "@tanstack/react-query";
import * as Location from "expo-location";
import { useRouter } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { Pressable, Text, View } from "react-native";
import MapView, { Marker, Region } from "react-native-maps";
import { placesApi, PlaceSummary } from "../../lib/api/places";

const CATEGORY_COLORS: Record<string, string> = {
  hotel: "#EF4444",
  restaurant: "#F97316",
  cafe: "#EAB308",
  scenic: "#22C55E",
  historical: "#A855F7",
  aesthetic: "#3B82F6",
};

export default function MapScreen() {
  const router = useRouter();
  const mapRef = useRef<MapView>(null);
  const [region, setRegion] = useState<Region>({
    latitude: 23.7806, longitude: 90.4074, latitudeDelta: 0.1, longitudeDelta: 0.1,
  });
  const [selected, setSelected] = useState<PlaceSummary | null>(null);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);

  useEffect(() => {
    Location.requestForegroundPermissionsAsync().then(({ status }) => {
      if (status === "granted") {
        Location.getCurrentPositionAsync({}).then((loc) => {
          setUserLocation({ lat: loc.coords.latitude, lng: loc.coords.longitude });
        });
      }
    });
  }, []);

  const radiusM = Math.max(region.latitudeDelta * 111000, 2000);
  const { data } = useQuery({
    queryKey: ["map-places", region.latitude.toFixed(3), region.longitude.toFixed(3)],
    queryFn: () => placesApi.list({ near_lat: region.latitude, near_lng: region.longitude, radius_m: Math.round(radiusM), limit: 50 }),
  });

  return (
    <View className="flex-1">
      <MapView
        ref={mapRef}
        style={{ flex: 1 }}
        initialRegion={region}
        onRegionChangeComplete={setRegion}
        showsUserLocation={!!userLocation}
      >
        {data?.items.map((place) => (
          <Marker
            key={place.id}
            coordinate={{ latitude: 0, longitude: 0 }}
            pinColor={CATEGORY_COLORS[place.category] ?? "#E91E63"}
            onPress={() => setSelected(place)}
          />
        ))}
      </MapView>

      {userLocation && (
        <Pressable
          className="absolute bottom-32 right-4 bg-white rounded-full p-3 shadow-md"
          onPress={() => mapRef.current?.animateToRegion({ latitude: userLocation.lat, longitude: userLocation.lng, latitudeDelta: 0.05, longitudeDelta: 0.05 })}
        >
          <Text className="text-lg">📍</Text>
        </Pressable>
      )}

      {selected && (
        <View className="absolute bottom-0 left-0 right-0 bg-white p-4 rounded-t-2xl shadow-lg">
          <Text className="font-bold text-lg">{selected.name}</Text>
          <Text className="text-gray-500 capitalize">{selected.category} · {selected.area}</Text>
          <Text className="text-yellow-500 mt-1">★ {selected.avg_rating.toFixed(1)}</Text>
          <Pressable className="bg-pink-600 rounded-xl py-3 mt-3 items-center" onPress={() => router.push(`/place/${selected.id}`)}>
            <Text className="text-white font-semibold">View Details</Text>
          </Pressable>
          <Pressable className="mt-2 items-center" onPress={() => setSelected(null)}>
            <Text className="text-gray-400">Close</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}
