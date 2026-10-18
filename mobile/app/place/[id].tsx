import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Clipboard from "expo-clipboard";
import * as Linking from "expo-linking";
import * as Location from "expo-location";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Platform, Pressable, ScrollView, Text, View } from "react-native";
import { showAlert } from "../../lib/alert";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";
import { Place, placesApi } from "../../lib/api/places";
import { reviewsApi } from "../../lib/api/reviews";
import HowToGetThere from "../../components/place/HowToGetThere";
import ReviewSummary from "../../components/place/ReviewSummary";
import ReviewCard from "../../components/reviews/ReviewCard";

const PRICE_LABELS: Record<string, string> = { budget: "৳", mid: "৳৳", luxury: "৳৳৳" };

export default function PlaceScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [locationDenied, setLocationDenied] = useState(false);

  useEffect(() => {
    Location.requestForegroundPermissionsAsync().then(({ status }) => {
      if (status === "granted") {
        Location.getCurrentPositionAsync({}).then((loc) =>
          setUserLocation({ lat: loc.coords.latitude, lng: loc.coords.longitude })
        );
      } else {
        setLocationDenied(true);
      }
    });
  }, []);

  const { data: place, isLoading, isError, refetch } = useQuery({
    queryKey: ["place", id],
    queryFn: () => placesApi.get(id),
    staleTime: 1000 * 60 * 5,
  });

  const { data: reviews } = useQuery({
    queryKey: ["reviews", id, "preview"],
    queryFn: () => reviewsApi.list(id),
  });

  const saveMutation = useMutation({
    mutationFn: (saved: boolean) => (saved ? placesApi.unsave(id) : placesApi.save(id)),
    onMutate: async (saved) => {
      await qc.cancelQueries({ queryKey: ["place", id] });
      const prev = qc.getQueryData<Place>(["place", id]);
      qc.setQueryData<Place>(["place", id], (p: Place | undefined) =>
        p && { ...p, is_saved_by_me: !saved, save_count: p.save_count + (saved ? -1 : 1) }
      );
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      qc.setQueryData(["place", id], ctx?.prev);
      showAlert("Couldn't update saved places");
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["saved-places"] }),
  });

  if (isLoading)
    return <View className="flex-1 items-center justify-center"><ActivityIndicator size="large" color="#E91E63" /></View>;

  if (isError || !place)
    return (
      <View className="flex-1 items-center justify-center px-8">
        <Text className="text-gray-500 text-center mb-4">Could not load place</Text>
        <Pressable onPress={() => refetch()}><Text className="text-pink-600 font-medium">Retry</Text></Pressable>
      </View>
    );

  return (
    <ScrollView className="flex-1 bg-white">
      {/* Hero */}
      <View className="relative">
        <Pressable className="absolute top-12 left-4 z-10 bg-black/40 rounded-full p-2" onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={20} color="white" />
        </Pressable>
        {place.cover_photo_url ? (
          <Image source={{ uri: place.cover_photo_url }} style={{ width: "100%", height: 288 }} contentFit="cover" />
        ) : (
          <View className="w-full h-72 bg-gray-200 items-center justify-center">
            <Text className="text-gray-400 text-4xl">📍</Text>
          </View>
        )}
      </View>

      <View className="px-4 py-4">
        {/* Header */}
        <View className="flex-row items-start mb-1">
          <View className="flex-1">
            <Text className="text-2xl font-bold">{place.name}</Text>
            <Text className="text-gray-500 capitalize">{place.category} · {place.area}, {place.district}</Text>
          </View>
          {place.is_verified && <Ionicons name="checkmark-circle" size={20} color="#E91E63" />}
        </View>

        {/* Rating */}
        <View className="flex-row items-center gap-2 mb-4">
          <Text className="text-yellow-500 font-semibold">★ {Number(place.avg_rating).toFixed(1)}</Text>
          <Text className="text-gray-400 text-sm">({place.review_count} reviews)</Text>
          {place.price_tier && <Text className="text-gray-500 font-medium">{PRICE_LABELS[place.price_tier]}</Text>}
        </View>

        {/* Actions */}
        <View className="flex-row gap-3 mb-6">
          <Pressable className="flex-1 border border-gray-200 rounded-xl py-3 items-center flex-row justify-center gap-2"
            onPress={() => saveMutation.mutate(place.is_saved_by_me)}>
            <Ionicons name={place.is_saved_by_me ? "bookmark" : "bookmark-outline"} size={18} color="#E91E63" />
            <Text className="text-pink-600 font-medium text-sm">{place.is_saved_by_me ? "Saved" : "Save"}</Text>
          </Pressable>
          <Pressable className="flex-1 bg-pink-600 rounded-xl py-3 items-center flex-row justify-center gap-2"
            onPress={() => router.push(`/place/${id}/review`)}>
            <Ionicons name="star-outline" size={18} color="white" />
            <Text className="text-white font-medium text-sm">Review</Text>
          </Pressable>
        </View>

        {/* Key info */}
        <View className="mb-4 gap-3">
          <Pressable className="flex-row items-center gap-3" onPress={() => Clipboard.setStringAsync(place.address)}>
            <Ionicons name="location-outline" size={18} color="#6B7280" />
            <Text className="text-gray-700 flex-1">{place.address}</Text>
            <Ionicons name="copy-outline" size={14} color="#9CA3AF" />
          </Pressable>
          {place.phone && (
            <Pressable className="flex-row items-center gap-3" onPress={() => Linking.openURL(`tel:${place.phone}`)}>
              <Ionicons name="call-outline" size={18} color="#6B7280" />
              <Text className="text-pink-600">{place.phone}</Text>
            </Pressable>
          )}
          {place.website && (
            <Pressable className="flex-row items-center gap-3" onPress={() => Linking.openURL(place.website!)}>
              <Ionicons name="globe-outline" size={18} color="#6B7280" />
              <Text className="text-pink-600 flex-1" numberOfLines={1}>{place.website}</Text>
            </Pressable>
          )}
        </View>

        {/* Amenities */}
        {place.amenities && place.amenities.length > 0 && (
          <View className="mb-6">
            <Text className="font-semibold mb-2">Amenities</Text>
            <View className="flex-row flex-wrap gap-2">
              {place.amenities.map((a) => (
                <View key={a} className="bg-gray-100 px-3 py-1 rounded-full">
                  <Text className="text-sm text-gray-600 capitalize">{a.replace("_", " ")}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* How to Get There */}
        {place.lat == null || place.lng == null ? null : userLocation ? (
          <HowToGetThere placeId={id} userLat={userLocation.lat} userLng={userLocation.lng} placeLat={place.lat} placeLng={place.lng} />
        ) : (
          <View className="bg-gray-50 rounded-xl p-4 mb-6">
            <Text className="font-semibold mb-1">How to Get There</Text>
            {locationDenied ? (
              <Text className="text-gray-500 text-sm">Allow location access in Settings to see bus, ride-hail and train options.</Text>
            ) : (
              <ActivityIndicator color="#E91E63" />
            )}
          </View>
        )}

        {/* Description */}
        {place.description && (
          <View className="mb-6">
            <Text className="font-semibold mb-2">About</Text>
            <Text className="text-gray-600 leading-relaxed">{place.description}</Text>
          </View>
        )}

        {/* AI review summary (web build only for now) */}
        {Platform.OS === "web" && <ReviewSummary placeId={id} />}

        {/* Reviews */}
        <View className="mb-8">
          <View className="flex-row items-center justify-between mb-2">
            <Text className="font-semibold text-lg">Reviews</Text>
            {place.review_count > 0 && (
              <Pressable onPress={() => router.push(`/place/${id}/reviews`)}>
                <Text className="text-pink-600 text-sm">See all {place.review_count}</Text>
              </Pressable>
            )}
          </View>
          {reviews?.items.length ? (
            reviews.items.slice(0, 3).map((r) => <ReviewCard key={r.id} review={r} />)
          ) : (
            <Text className="text-gray-400 text-sm">No reviews yet — be the first.</Text>
          )}
        </View>
      </View>
    </ScrollView>
  );
}
