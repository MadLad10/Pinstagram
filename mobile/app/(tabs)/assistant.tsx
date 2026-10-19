import { Ionicons } from "@expo/vector-icons";
import * as Location from "expo-location";
import { useRouter } from "expo-router";
import { Fragment, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Platform, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import {
  AssistantEvent,
  AssistantHttpError,
  ChatTurn,
  SourcePlace,
  SourceRoute,
  streamChat,
} from "../../lib/api/ai";

interface Step {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  status: "running" | "ok" | "error";
  summary?: string;
}

interface Turn {
  role: "user" | "assistant";
  content: string;
  steps?: Step[];
  places?: SourcePlace[];
  routes?: SourceRoute[];
  error?: string;
  streaming?: boolean;
}

const SUGGESTIONS = [
  "Cheapest way from Mirpur 10 to a good biryani place in Old Dhaka",
  "A quiet cafe in Dhanmondi with good wifi",
  "Something historical to see near Lalbagh, and how to get there by bus",
];

const TOOL_LABELS: Record<string, string> = {
  search_places: "Searching places",
  get_place_details: "Reading place details",
  get_fare: "Comparing fares",
  get_bus_route: "Finding a bus",
  get_ridehail_estimate: "Ride-hail estimate",
};

const MODE_ICONS: Record<SourceRoute["mode"], string> = { bus: "🚌", ride_hail: "🚗", train: "🚆", walk: "🚶" };

function stepDetail(step: Step): string {
  const a = step.arguments as Record<string, string | undefined>;
  if (step.name === "search_places") return [a.query, a.near && `near ${a.near}`].filter(Boolean).join(" ");
  if (a.origin && a.place) return `${a.origin} → ${a.place}`;
  return a.place ?? "";
}

/** Bold (**x**) inside a line. */
function Inline({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
        part.startsWith("**") && part.endsWith("**") ? (
          <Text key={i} className="font-semibold">{part.slice(2, -2)}</Text>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        )
      )}
    </>
  );
}

/** Just enough Markdown for model answers: paragraphs, bullets, numbered lists, headings, bold. */
function Answer({ text }: { text: string }) {
  return (
    <View className="gap-1.5">
      {text.split("\n").map((raw, i) => {
        const line = raw.trimEnd();
        if (!line.trim()) return <View key={i} className="h-1" />;
        const heading = line.match(/^#{1,4}\s+(.*)$/);
        if (heading)
          return (
            <Text key={i} className="font-semibold text-gray-900 mt-1">
              <Inline text={heading[1]} />
            </Text>
          );
        const bullet = line.match(/^(\s*)(?:[-*•]|(\d+)[.)])\s+(.*)$/);
        if (bullet)
          return (
            <View key={i} className="flex-row" style={{ paddingLeft: bullet[1].length > 1 ? 16 : 0 }}>
              <Text className="text-gray-500 w-5">{bullet[2] ? `${bullet[2]}.` : "•"}</Text>
              <Text className="text-gray-800 flex-1 leading-5">
                <Inline text={bullet[3]} />
              </Text>
            </View>
          );
        return (
          <Text key={i} className="text-gray-800 leading-5">
            <Inline text={line} />
          </Text>
        );
      })}
    </View>
  );
}

function StepChip({ step }: { step: Step }) {
  const icon = step.status === "ok" ? "checkmark-circle" : step.status === "error" ? "alert-circle" : null;
  const color = step.status === "ok" ? "#059669" : "#D97706";
  const detail = stepDetail(step);
  return (
    <View className="flex-row items-start gap-2 bg-gray-50 border border-gray-100 rounded-lg px-3 py-2">
      {icon ? (
        <Ionicons name={icon} size={16} color={color} style={{ marginTop: 1 }} />
      ) : (
        <ActivityIndicator size="small" color="#E91E63" />
      )}
      <View className="flex-1">
        <Text className="text-sm text-gray-700">
          <Text className="font-medium">{TOOL_LABELS[step.name] ?? step.name}</Text>
          {detail ? <Text className="text-gray-500"> · {detail}</Text> : null}
        </Text>
        {step.summary && (
          <Text className="text-xs text-gray-500 mt-0.5" numberOfLines={2}>
            {step.summary}
          </Text>
        )}
      </View>
    </View>
  );
}

function routeLine(r: SourceRoute): string {
  const fare = r.fare_bdt ? `৳${r.fare_bdt}` : "free";
  if (r.mode === "bus") return `${r.bus}: ${r.board_at} → ${r.get_off_at} · ${fare} · ${r.duration_min} min`;
  if (r.mode === "train") return `${r.from_station} → ${r.to_station} · ${fare} · ${r.duration_min} min`;
  if (r.mode === "ride_hail") return `Ride-hail from ${fare} · ${r.duration_min} min`;
  return `Walk · ${r.duration_min} min`;
}

function PlaceCard({ place, routes }: { place: SourcePlace; routes: SourceRoute[] }) {
  const router = useRouter();
  const mine = routes.filter((r) => r.place_id === place.id).sort((a, b) => a.fare_bdt - b.fare_bdt);
  return (
    <Pressable
      className="border border-gray-200 rounded-xl p-3 bg-white"
      onPress={() => router.push(`/place/${place.id}`)}
    >
      <View className="flex-row items-center">
        <Text className="font-semibold flex-1" numberOfLines={1}>{place.name}</Text>
        <Ionicons name="chevron-forward" size={16} color="#9CA3AF" />
      </View>
      <Text className="text-xs text-gray-500 capitalize mt-0.5">
        {place.category}
        {place.area ? ` · ${place.area}` : ""}
        {place.avg_rating ? ` · ★ ${place.avg_rating.toFixed(1)}` : ""}
      </Text>
      {mine.length > 0 && (
        <View className="mt-2 gap-1">
          <Text className="text-xs text-gray-400">From {mine[0].origin}</Text>
          {mine.slice(0, 3).map((r, i) => (
            <Text key={i} className="text-xs text-gray-700" numberOfLines={1}>
              {MODE_ICONS[r.mode]} {routeLine(r)}
            </Text>
          ))}
        </View>
      )}
    </Pressable>
  );
}

function AssistantTurn({ turn }: { turn: Turn }) {
  const thinking = turn.streaming && !turn.content && !turn.steps?.some((s) => s.status === "running");
  return (
    <View className="gap-2">
      {turn.steps && turn.steps.length > 0 && (
        <View className="gap-1.5">
          {turn.steps.map((s) => <StepChip key={s.id} step={s} />)}
        </View>
      )}
      {thinking && (
        <View className="flex-row items-center gap-2">
          <ActivityIndicator size="small" color="#E91E63" />
          <Text className="text-sm text-gray-500">Thinking…</Text>
        </View>
      )}
      {turn.content ? <Answer text={turn.content} /> : null}
      {turn.error && (
        <View className="flex-row items-center gap-2 bg-amber-50 rounded-lg px-3 py-2">
          <Ionicons name="warning-outline" size={16} color="#D97706" />
          <Text className="text-sm text-amber-800 flex-1">{turn.error}</Text>
        </View>
      )}
      {turn.places && turn.places.length > 0 && (
        <View className="gap-2 mt-1">
          {turn.places.map((p) => <PlaceCard key={p.id} place={p} routes={turn.routes ?? []} />)}
        </View>
      )}
    </View>
  );
}

export default function AssistantScreen() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [locating, setLocating] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<ScrollView>(null);
  const busy = turns.at(-1)?.streaming ?? false;

  useEffect(() => () => abortRef.current?.abort(), []);

  const toggleLocation = async () => {
    if (location) return setLocation(null);
    setLocating(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status === "granted") {
        const pos = await Location.getCurrentPositionAsync({});
        setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      }
    } catch {
      // Location is optional; the assistant asks where the trip starts.
    } finally {
      setLocating(false);
    }
  };

  // Mutate the assistant turn being streamed (always the last one).
  const updateLast = (fn: (t: Turn) => Turn) =>
    setTurns((ts) => [...ts.slice(0, -1), fn(ts[ts.length - 1])]);

  const onEvent = (e: AssistantEvent) => {
    switch (e.type) {
      case "token":
        return updateLast((t) => ({ ...t, content: t.content + e.data.text }));
      case "tool_call":
        return updateLast((t) => ({
          ...t,
          steps: [...(t.steps ?? []), { id: e.data.id, name: e.data.name, arguments: e.data.arguments, status: "running" }],
        }));
      case "tool_result":
        return updateLast((t) => ({
          ...t,
          steps: t.steps?.map((s) =>
            s.id === e.data.id ? { ...s, status: e.data.ok ? "ok" : "error", summary: e.data.summary } : s
          ),
        }));
      case "sources":
        return updateLast((t) => ({ ...t, places: e.data.places, routes: e.data.routes }));
      case "error":
        return updateLast((t) => ({ ...t, error: e.data.message }));
      case "done":
        return updateLast((t) => ({ ...t, streaming: false }));
    }
  };

  const send = async (text: string) => {
    const content = text.trim();
    if (!content || busy) return;
    // The server keeps no history: send the conversation so far. Empty
    // assistant turns (failed requests) aren't valid messages.
    const history: ChatTurn[] = [
      ...turns.filter((t) => t.content.trim()).map((t) => ({ role: t.role, content: t.content })),
      { role: "user", content },
    ];
    setInput("");
    setTurns((ts) => [...ts, { role: "user", content }, { role: "assistant", content: "", steps: [], streaming: true }]);

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await streamChat(history, location, onEvent, controller.signal);
    } catch (err) {
      if (!controller.signal.aborted)
        updateLast((t) => ({
          ...t,
          error: err instanceof AssistantHttpError ? err.message : "Couldn't reach the assistant. Check your connection.",
        }));
    } finally {
      updateLast((t) => ({
        ...t,
        streaming: false,
        steps: t.steps?.map((s) => (s.status === "running" ? { ...s, status: "error" } : s)),
      }));
      if (abortRef.current === controller) abortRef.current = null;
    }
  };

  const stop = () => abortRef.current?.abort();

  if (Platform.OS !== "web")
    return (
      <View className="flex-1 items-center justify-center bg-white px-8">
        <Text className="text-gray-500 text-center">The trip assistant is available on the web app.</Text>
      </View>
    );

  return (
    <View className="flex-1 bg-white">
      <View className="px-4 pt-12 pb-3 border-b border-gray-100 flex-row items-center gap-2">
        <Ionicons name="sparkles" size={20} color="#E91E63" />
        <Text className="text-xl font-bold flex-1">Trip assistant</Text>
        {turns.length > 0 && !busy && (
          <Pressable onPress={() => setTurns([])} className="px-2 py-1">
            <Text className="text-pink-600 text-sm">New chat</Text>
          </Pressable>
        )}
      </View>

      <ScrollView
        ref={scrollRef}
        className="flex-1"
        contentContainerStyle={{ padding: 16, gap: 16, maxWidth: 720, width: "100%", alignSelf: "center" }}
        onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
      >
        {turns.length === 0 && (
          <View className="mt-6 gap-3">
            <Text className="text-gray-600">
              Ask where to go in Dhaka and how to get there. Answers use Pinstagram's places, reviews, bus routes and
              fares.
            </Text>
            {SUGGESTIONS.map((s) => (
              <Pressable key={s} onPress={() => send(s)} className="border border-gray-200 rounded-xl px-4 py-3">
                <Text className="text-gray-700">{s}</Text>
              </Pressable>
            ))}
          </View>
        )}
        {turns.map((t, i) =>
          t.role === "user" ? (
            <View key={i} className="self-end bg-pink-600 rounded-2xl rounded-br-sm px-4 py-2.5 max-w-[85%]">
              <Text className="text-white">{t.content}</Text>
            </View>
          ) : (
            <AssistantTurn key={i} turn={t} />
          )
        )}
      </ScrollView>

      <View className="border-t border-gray-100 px-4 py-3" style={{ maxWidth: 720, width: "100%", alignSelf: "center" }}>
        <Pressable onPress={toggleLocation} className="flex-row items-center gap-1.5 mb-2 self-start">
          {locating ? (
            <ActivityIndicator size="small" color="#E91E63" />
          ) : (
            <Ionicons name={location ? "navigate" : "navigate-outline"} size={14} color={location ? "#E91E63" : "#6B7280"} />
          )}
          <Text className={`text-xs ${location ? "text-pink-600" : "text-gray-500"}`}>
            {location ? "Using your location as the starting point" : "Use my location"}
          </Text>
        </Pressable>
        <View className="flex-row items-center gap-2">
          <TextInput
            className="flex-1 bg-gray-100 rounded-xl px-4 py-3 text-base"
            placeholder="Where do you want to go?"
            value={input}
            onChangeText={setInput}
            onSubmitEditing={() => send(input)}
            submitBehavior="submit"
            editable={!busy}
            maxLength={2000}
          />
          {busy ? (
            <Pressable onPress={stop} className="bg-gray-800 rounded-full p-3" accessibilityLabel="Stop">
              <Ionicons name="stop" size={18} color="white" />
            </Pressable>
          ) : (
            <Pressable
              onPress={() => send(input)}
              disabled={!input.trim()}
              className={`rounded-full p-3 ${input.trim() ? "bg-pink-600" : "bg-gray-200"}`}
              accessibilityLabel="Send"
            >
              <Ionicons name="arrow-up" size={18} color="white" />
            </Pressable>
          )}
        </View>
      </View>
    </View>
  );
}
