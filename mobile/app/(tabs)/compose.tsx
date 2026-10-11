import * as ImagePicker from "expo-image-picker";
import { useQueryClient } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { showAlert } from "../../lib/alert";
import PlacePicker from "../../components/PlacePicker";
import { PlaceSummary } from "../../lib/api/places";
import { postsApi } from "../../lib/api/posts";
import { prepareUpload } from "../../lib/upload";

const MAX_BYTES = 50 * 1024 * 1024;

function contentTypeFor(asset: ImagePicker.ImagePickerAsset): string {
  if (asset.mimeType) return asset.mimeType;
  if (asset.type === "video") return "video/mp4";
  return asset.uri.toLowerCase().endsWith(".png") ? "image/png" : "image/jpeg";
}

export default function ComposeScreen() {
  const router = useRouter();
  const qc = useQueryClient();
  const [media, setMedia] = useState<ImagePicker.ImagePickerAsset | null>(null);
  const [place, setPlace] = useState<PlaceSummary | null>(null);
  const [caption, setCaption] = useState("");
  const [price, setPrice] = useState("");
  const [progress, setProgress] = useState<number | null>(null);

  const pickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images", "videos"],
      quality: 0.8,
      allowsEditing: true,
      aspect: [1, 1],
    });
    if (result.canceled) return;
    const asset = result.assets[0];
    if (asset.fileSize && asset.fileSize > MAX_BYTES) {
      showAlert("File too large", "Please pick something under 50 MB.");
      return;
    }
    setMedia(asset);
  };

  const reset = () => {
    setMedia(null);
    setPlace(null);
    setCaption("");
    setPrice("");
  };

  const handlePost = async () => {
    if (!media || !place) {
      showAlert("Missing info", "Pick a photo and tag a place.");
      return;
    }
    setProgress(0);
    try {
      const contentType = contentTypeFor(media);
      const filename = media.fileName ?? media.uri.split("/").pop() ?? "upload.jpg";
      const upload = await prepareUpload(media.uri, media.fileSize);
      const { upload_url, file_key } = await postsApi.presign(filename, contentType, upload.size);
      await upload.send(upload_url, contentType, setProgress);

      const hashtags = Array.from(caption.matchAll(/#(\w+)/g), (m) => m[1]);
      await postsApi.create({
        place_id: place.id,
        file_key,
        media_type: media.type === "video" ? "video" : "image",
        caption: caption.trim() || undefined,
        hashtags: hashtags.length ? hashtags : undefined,
        price_mentioned: price ? parseInt(price, 10) : undefined,
      });

      qc.invalidateQueries({ queryKey: ["my-posts"] });
      reset();
      showAlert("Posted!", "Your post will appear in feeds once a moderator approves it.");
      router.replace("/(tabs)/profile");
    } catch (e: any) {
      showAlert("Upload failed", e?.response?.data?.detail ?? e?.message ?? "Please try again.");
    } finally {
      setProgress(null);
    }
  };

  const uploading = progress !== null;

  return (
    <ScrollView className="flex-1 bg-white" keyboardShouldPersistTaps="handled">
      <View className="px-4 pt-12 pb-8">
        <Text className="text-xl font-bold mb-6">New Post</Text>

        <Pressable
          className="w-full aspect-square bg-gray-100 rounded-2xl items-center justify-center mb-4 overflow-hidden"
          onPress={pickImage}
          disabled={uploading}
        >
          {media ? (
            <Image source={{ uri: media.uri }} style={{ width: "100%", height: "100%" }} contentFit="cover" />
          ) : (
            <Text className="text-gray-400 text-lg">Tap to pick a photo or video</Text>
          )}
        </Pressable>

        <PlacePicker value={place} onChange={setPlace} />

        <TextInput
          className="border border-gray-200 rounded-xl px-4 py-3 mb-3 min-h-[80px]"
          placeholder="Caption — add #hashtags"
          value={caption}
          onChangeText={setCaption}
          multiline
          maxLength={2200}
          textAlignVertical="top"
        />

        <TextInput
          className="border border-gray-200 rounded-xl px-4 py-3 mb-6"
          placeholder="How much did you spend? ৳ (optional)"
          value={price}
          onChangeText={(t) => setPrice(t.replace(/\D/g, ""))}
          keyboardType="number-pad"
        />

        {uploading && (
          <View className="mb-4">
            <View className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <View className="h-2 bg-pink-600" style={{ width: `${Math.round(progress! * 100)}%` }} />
            </View>
            <Text className="text-xs text-gray-500 mt-1">Uploading… {Math.round(progress! * 100)}%</Text>
          </View>
        )}

        <Pressable
          className={`rounded-xl py-4 items-center ${media && place ? "bg-pink-600" : "bg-gray-200"}`}
          onPress={handlePost}
          disabled={uploading}
        >
          {uploading ? (
            <ActivityIndicator color="white" />
          ) : (
            <Text className={`font-semibold text-base ${media && place ? "text-white" : "text-gray-400"}`}>Post</Text>
          )}
        </Pressable>
      </View>
    </ScrollView>
  );
}
