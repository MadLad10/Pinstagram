import * as ImagePicker from "expo-image-picker";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, Image, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { postsApi } from "../../lib/api/posts";

export default function ComposeScreen() {
  const router = useRouter();
  const [media, setMedia] = useState<ImagePicker.ImagePickerAsset | null>(null);
  const [placeId, setPlaceId] = useState("");
  const [caption, setCaption] = useState("");
  const [price, setPrice] = useState("");
  const [loading, setLoading] = useState(false);

  const pickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.All,
      quality: 0.8,
    });
    if (!result.canceled) setMedia(result.assets[0]);
  };

  const handlePost = async () => {
    if (!media || !placeId) {
      Alert.alert("Missing info", "Please select a photo and tag a place.");
      return;
    }
    setLoading(true);
    try {
      const filename = media.uri.split("/").pop() ?? "photo.jpg";
      const contentType = media.type === "video" ? "video/mp4" : "image/jpeg";
      const { upload_url, file_key } = await postsApi.presign(filename, contentType, media.fileSize ?? 1000000);

      const blob = await fetch(media.uri).then((r) => r.blob());
      await fetch(upload_url, { method: "PUT", body: blob, headers: { "Content-Type": contentType } });

      await postsApi.create({
        place_id: placeId,
        file_key,
        media_type: media.type === "video" ? "video" : "image",
        caption: caption || undefined,
        price_mentioned: price ? parseInt(price) : undefined,
      });

      Alert.alert("Posted!", "Your post will appear once approved.");
      router.replace("/(tabs)");
    } catch (e: any) {
      Alert.alert("Upload failed", e?.response?.data?.detail ?? "Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView className="flex-1 bg-white">
      <View className="px-4 pt-12 pb-8">
        <Text className="text-xl font-bold mb-6">New Post</Text>

        <Pressable className="w-full aspect-square bg-gray-100 rounded-2xl items-center justify-center mb-4 overflow-hidden" onPress={pickImage}>
          {media ? (
            <Image source={{ uri: media.uri }} className="w-full h-full" resizeMode="cover" />
          ) : (
            <Text className="text-gray-400 text-lg">Tap to pick photo or video</Text>
          )}
        </Pressable>

        <TextInput
          className="border border-gray-200 rounded-xl px-4 py-3 mb-3"
          placeholder="Place ID (search coming soon)"
          value={placeId}
          onChangeText={setPlaceId}
          autoCapitalize="none"
        />

        <TextInput
          className="border border-gray-200 rounded-xl px-4 py-3 mb-3"
          placeholder="Caption (optional)"
          value={caption}
          onChangeText={setCaption}
          multiline
        />

        <TextInput
          className="border border-gray-200 rounded-xl px-4 py-3 mb-6"
          placeholder="Price in ৳ (optional)"
          value={price}
          onChangeText={setPrice}
          keyboardType="number-pad"
        />

        <Pressable className="bg-pink-600 rounded-xl py-4 items-center" onPress={handlePost} disabled={loading}>
          {loading ? <ActivityIndicator color="white" /> : <Text className="text-white font-semibold text-base">Post</Text>}
        </Pressable>
      </View>
    </ScrollView>
  );
}
