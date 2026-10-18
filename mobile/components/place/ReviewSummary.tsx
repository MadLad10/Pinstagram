import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { ActivityIndicator, Text, View } from "react-native";
import { aiApi, SummaryPoint } from "../../lib/api/ai";

const SECTIONS: { key: "pros" | "cons" | "best_for"; title: string; icon: string; color: string }[] = [
  { key: "pros", title: "People like", icon: "thumbs-up-outline", color: "#059669" },
  { key: "cons", title: "Watch out for", icon: "alert-circle-outline", color: "#D97706" },
  { key: "best_for", title: "Best for", icon: "people-outline", color: "#E91E63" },
];

function Point({ point }: { point: SummaryPoint }) {
  return (
    <View className="flex-row mt-1.5">
      <Text className="text-gray-400 mr-2">•</Text>
      <Text className="text-gray-700 flex-1 text-sm leading-5">{point.text}</Text>
      <Text className="text-gray-400 text-xs ml-2">
        {point.review_ids.length} {point.review_ids.length === 1 ? "review" : "reviews"}
      </Text>
    </View>
  );
}

/** "What reviewers say": an AI summary where every point cites its reviews. */
export default function ReviewSummary({ placeId }: { placeId: string }) {
  const { data } = useQuery({
    queryKey: ["summary", placeId],
    queryFn: () => aiApi.summary(placeId),
    // Generated in the background on first request; check back until ready.
    refetchInterval: (q) => (q.state.data?.status === "pending" ? 5000 : false),
  });

  if (!data || data.status === "disabled" || data.status === "not_enough_reviews") return null;

  return (
    <View className="bg-pink-50/60 border border-pink-100 rounded-xl p-4 mb-6">
      <View className="flex-row items-center gap-2 mb-1">
        <Ionicons name="sparkles" size={16} color="#E91E63" />
        <Text className="font-semibold flex-1">What reviewers say</Text>
      </View>

      {data.status === "pending" ? (
        <View className="flex-row items-center gap-2 mt-2">
          <ActivityIndicator size="small" color="#E91E63" />
          <Text className="text-gray-500 text-sm">Summarizing reviews…</Text>
        </View>
      ) : (
        <>
          {SECTIONS.filter((s) => data[s.key].length > 0).map((s) => (
            <View key={s.key} className="mt-3">
              <View className="flex-row items-center gap-1.5">
                <Ionicons name={s.icon as any} size={14} color={s.color} />
                <Text className="text-xs font-semibold uppercase tracking-wide" style={{ color: s.color }}>
                  {s.title}
                </Text>
              </View>
              {data[s.key].map((p) => <Point key={p.text} point={p} />)}
            </View>
          ))}
          <Text className="text-xs text-gray-400 mt-3">
            AI summary of {data.based_on_reviews} reviews{data.stale ? " · updating with newer reviews" : ""}
          </Text>
        </>
      )}
    </View>
  );
}
