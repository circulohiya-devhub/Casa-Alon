"use client";

import { useRef, useState, useEffect, FormEvent } from "react";

type Message = {
  role: "user" | "assistant";
  content: string;
};

const GREETING: Message = {
  role: "assistant",
  content:
    "Hi, I'm Ask Alon. I can tell you about rooms, rates, amenities, or how to get here — what do you want to know?",
};

const SESSION_STORAGE_KEY = "casa-alon-session-id";

function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let id = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(SESSION_STORAGE_KEY, id);
  }
  return id;
}

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // On mount: grab (or create) this visitor's session ID, then try to
  // restore their previous conversation from Redis. If Redis isn't
  // configured, or there's nothing stored yet, this just no-ops and the
  // greeting stays as-is.
  useEffect(() => {
    const id = getSessionId();
    setSessionId(id);
    if (!id) return;

    fetch(`/api/chat?sessionId=${encodeURIComponent(id)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data: { history?: Message[] } | null) => {
        if (data?.history && data.history.length > 0) {
          setMessages([GREETING, ...data.history]);
        }
      })
      .catch(() => {
        // No stored history available — fine, keep the greeting.
      });
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, open]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const nextMessages = [...messages, { role: "user" as const, content: text }];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          sessionId,
          // Sent as a fallback only — if Redis has stored history for
          // this session, the server prefers that over this.
          history: nextMessages.slice(0, -1),
        }),
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.error || "Request failed");

      setMessages([
        ...nextMessages,
        { role: "assistant", content: data.reply as string },
      ]);
    } catch {
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content:
            "Sorry, something went wrong on my end. Please try again, or email stay@casaalon.com.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed bottom-5 right-5 z-40 md:bottom-8 md:right-8">
      {open && (
        <div className="mb-3 flex h-[28rem] w-[22rem] max-w-[calc(100vw-2.5rem)] flex-col overflow-hidden rounded-lg border border-tide/15 bg-foam shadow-xl">
          <div className="flex items-center justify-between bg-tide px-4 py-3">
            <span className="font-display text-foam">Ask Alon</span>
            <button
              onClick={() => setOpen(false)}
              aria-label="Close chat"
              className="text-foam/70 transition-colors hover:text-foam"
            >
              &times;
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                  m.role === "user"
                    ? "ml-auto bg-gold text-ink"
                    : "bg-sand text-ink"
                }`}
              >
                {m.content}
              </div>
            ))}
            {loading && (
              <div className="max-w-[85%] rounded-lg bg-sand px-3 py-2 text-sm text-ink/50">
                Thinking…
              </div>
            )}
          </div>

          <form
            onSubmit={handleSubmit}
            className="flex items-center gap-2 border-t border-tide/10 p-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about rooms, rates, amenities…"
              className="flex-1 rounded-full border border-tide/15 bg-white px-4 py-2 text-sm text-ink outline-none focus-visible:border-gold"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="rounded-full bg-tide px-4 py-2 text-sm text-foam disabled:opacity-40"
            >
              Send
            </button>
          </form>
        </div>
      )}

      <button
        onClick={() => setOpen((v) => !v)}
        className="flex h-14 w-14 items-center justify-center rounded-full bg-gold text-ink shadow-lg transition-transform hover:scale-105"
        aria-label={open ? "Close chat" : "Chat with Ask Alon"}
      >
        {open ? (
          <span className="text-2xl leading-none">&times;</span>
        ) : (
          <span className="font-display text-sm">Alon</span>
        )}
      </button>
    </div>
  );
}
