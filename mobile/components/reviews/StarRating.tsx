import { Pressable, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

interface Props {
  value: number;
  onChange?: (v: number) => void;
  size?: number;
}

export default function StarRating({ value, onChange, size = 28 }: Props) {
  return (
    <View className="flex-row gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <Pressable key={star} onPress={() => onChange?.(star)} disabled={!onChange}>
          <Ionicons
            name={star <= value ? "star" : "star-outline"}
            size={size}
            color={star <= value ? "#F59E0B" : "#D1D5DB"}
          />
        </Pressable>
      ))}
    </View>
  );
}
