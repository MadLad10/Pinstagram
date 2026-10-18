import { storage } from "../storage";
import { authApi } from "./auth";
import { api, BASE_URL } from "./client";
import { PlaceSummary } from "./places";

// --------------------------------------------------------------- hybrid search

export interface HybridPlace extends PlaceSummary {
  score: number;
  match: { semantic: boolean; keyword: boolean; review_snippet: string | null };
}

export interface HybridFilters {
  category?: string;
  price_tier?: string;
  area?: string;
}

// ------------------------------------------------------------- review summary

export interface SummaryPoint { text: string; review_ids: string[] }

export interface ReviewSummary {
  status: "ready" | "pending" | "not_enough_reviews" | "disabled";
  pros: SummaryPoint[];
  cons: SummaryPoint[];
  best_for: SummaryPoint[];
  based_on_reviews: number;
  generated_at: string | null;
  model: string | null;
  stale: boolean;
}

export const aiApi = {
  hybridSearch: (q: string, filters: HybridFilters = {}) =>
    api
      .get<{ items: HybridPlace[]; mode: "hybrid" | "keyword" }>("/search/hybrid", { params: { q, ...filters, limit: 20 } })
      .then((r) => r.data),

  summary: (placeId: string) => api.get<ReviewSummary>(`/places/${placeId}/summary`).then((r) => r.data),
};

// ------------------------------------------------------------------ assistant

export interface ChatTurn { role: "user" | "assistant"; content: string }

export interface SourcePlace { id: string; name: string; category: string; area: string | null; avg_rating: number }

export interface SourceRoute {
  place_id: string;
  place_name: string;
  origin: string;
  mode: "bus" | "ride_hail" | "train" | "walk";
  fare_bdt: number;
  duration_min: number;
  bus?: string;
  board_at?: string;
  get_off_at?: string;
  from_station?: string;
  to_station?: string;
  label?: string;
}

export type AssistantEvent =
  | { type: "token"; data: { text: string } }
  | { type: "tool_call"; data: { id: string; name: string; arguments: Record<string, unknown> } }
  | { type: "tool_result"; data: { id: string; name: string; ok: boolean; summary: string } }
  | { type: "sources"; data: { places: SourcePlace[]; routes: SourceRoute[] } }
  | { type: "error"; data: { code: string; message: string } }
  | { type: "done"; data: { finish_reason: string; steps?: number; tool_calls?: number } };

export class AssistantHttpError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function post(body: unknown, signal: AbortSignal) {
  const token = await storage.get("access_token");
  return fetch(`${BASE_URL}/assistant/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  });
}

/**
 * Stream the assistant's reply. EventSource can't POST, so this reads the
 * Server-Sent Events off a fetch body. Web only: React Native's fetch has no
 * streaming body.
 */
export async function streamChat(
  messages: ChatTurn[],
  location: { lat: number; lng: number } | null,
  onEvent: (event: AssistantEvent) => void,
  signal: AbortSignal
): Promise<void> {
  const body = { messages, location };
  let res = await post(body, signal);
  if (res.status === 401) {
    // An authenticated axios call refreshes the token through the interceptor.
    await authApi.getMe();
    res = await post(body, signal);
  }
  if (!res.ok || !res.body) {
    const detail = await res.json().then((j) => j.detail).catch(() => null);
    throw new AssistantHttpError(res.status, typeof detail === "string" ? detail : "The assistant is unavailable.");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let end;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      let type = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) type = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      }
      if (data.length) onEvent({ type, data: JSON.parse(data.join("\n")) } as AssistantEvent);
    }
  }
}
