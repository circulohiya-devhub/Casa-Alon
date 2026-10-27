import { Redis } from "@upstash/redis";

export type ChatTurn = {
  role: "user" | "assistant";
  content: string;
};

// How long a conversation is kept, and how many turns of it.
const HISTORY_TTL_SECONDS = 60 * 60 * 24 * 7; // 7 days
const MAX_TURNS = 20;

/**
 * Redis is optional. If the two env vars below aren't set, every function
 * here quietly no-ops instead of throwing — the chatbot still works, it
 * just falls back to the browser-only, in-memory history it had before
 * (resets on page reload) rather than persisting across visits.
 */
export function isRedisConfigured(): boolean {
  return Boolean(
    process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN
  );
}

function getClient(): Redis | null {
  if (!isRedisConfigured()) return null;
  return new Redis({
    url: process.env.UPSTASH_REDIS_REST_URL!,
    token: process.env.UPSTASH_REDIS_REST_TOKEN!,
  });
}

function keyFor(sessionId: string): string {
  return `casa-alon:chat:${sessionId}`;
}

export async function loadHistory(sessionId: string): Promise<ChatTurn[]> {
  const client = getClient();
  if (!client || !sessionId) return [];
  try {
    const data = await client.get<ChatTurn[]>(keyFor(sessionId));
    return Array.isArray(data) ? data : [];
  } catch (err) {
    console.error("Redis loadHistory error:", err);
    return [];
  }
}

export async function saveHistory(
  sessionId: string,
  turns: ChatTurn[]
): Promise<void> {
  const client = getClient();
  if (!client || !sessionId) return;
  try {
    const trimmed = turns.slice(-MAX_TURNS);
    await client.set(keyFor(sessionId), trimmed, { ex: HISTORY_TTL_SECONDS });
  } catch (err) {
    console.error("Redis saveHistory error:", err);
  }
}
