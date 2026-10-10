import { useEffect, useRef } from "react";
import { Animated, View } from "react-native";

/** Pulsing placeholder cards shown while the first page of a feed loads. */
export default function FeedSkeleton({ count = 2 }: { count?: number }) {
  const opacity = useRef(new Animated.Value(0.5)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.5, duration: 700, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);

  return (
    <Animated.View style={{ opacity }}>
      {Array.from({ length: count }).map((_, i) => (
        <View key={i} className="bg-white mb-2">
          <View className="flex-row items-center px-4 py-3">
            <View className="w-9 h-9 rounded-full bg-gray-200 mr-3" />
            <View className="flex-1 gap-1.5">
              <View className="h-3 w-28 bg-gray-200 rounded" />
              <View className="h-2.5 w-40 bg-gray-100 rounded" />
            </View>
          </View>
          <View className="w-full aspect-square bg-gray-200" />
          <View className="px-4 py-3 gap-2">
            <View className="h-3 w-20 bg-gray-200 rounded" />
            <View className="h-3 w-3/4 bg-gray-100 rounded" />
          </View>
        </View>
      ))}
    </Animated.View>
  );
}
