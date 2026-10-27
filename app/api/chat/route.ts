import { NextRequest, NextResponse } from "next/server";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import {
  HumanMessage,
  AIMessage,
  SystemMessage,
} from "@langchain/core/messages";
import { traceable } from "langsmith/traceable";
import { retrieveContext } from "@/lib/rag";
import { loadHistory, saveHistory, ChatTurn } from "@/lib/redis";

// LangChain's Google GenAI packages need Node APIs, so this can't run on
// the Edge runtime.
export const runtime = "nodejs";

const SYSTEM_PROMPT = `You are "Ask Alon," the guest-facing assistant for Casa Alon, a small
boutique hotel in Puerto Princesa, Palawan.

Answer only using the CONTEXT provided below plus the conversation so far.
If the answer isn't in the context, say you're not sure and suggest the
guest email stay@casaalon.com — never invent rates, dates, or policies.
Keep answers short, warm, and specific. You are not able to make or modify
a booking yourself; direct booking requests to the contact email or phone
number.`;

/**
 * The actual RAG + chat logic, wrapped below in traceable() so each call
 * shows up as a single named run in LangSmith (when LANGCHAIN_TRACING_V2
 * and LANGCHAIN_API_KEY are set — otherwise traceable() is a harmless
 * passthrough).
 */
async function answerQuestion(params: {
  sessionId: string;
  message: string;
  clientHistory: ChatTurn[];
}): Promise<{ reply: string; history: ChatTurn[] }> {
  const { sessionId, message, clientHistory } = params;

  // Redis is the source of truth when it's configured and has something
  // stored; otherwise fall back to whatever history the browser sent.
  const storedHistory = await loadHistory(sessionId);
  const history = storedHistory.length > 0 ? storedHistory : clientHistory;

  const contextDocs = await retrieveContext(message);
  const context = contextDocs
    .map((doc) => `- (${doc.metadata.topic}) ${doc.pageContent}`)
    .join("\n");

  const model = new ChatGoogleGenerativeAI({
    apiKey: process.env.GOOGLE_API_KEY,
    model: "gemini-3.1-flash-lite",
    temperature: 0.3,
  });

  const messages = [
    new SystemMessage(`${SYSTEM_PROMPT}\n\nCONTEXT:\n${context}`),
    ...history
      .slice(-10)
      .map((turn) =>
        turn.role === "user"
          ? new HumanMessage(turn.content)
          : new AIMessage(turn.content)
      ),
    new HumanMessage(message),
  ];

  const response = await model.invoke(messages);
  const reply = response.content as string;

  const updatedHistory: ChatTurn[] = [
    ...history,
    { role: "user", content: message },
    { role: "assistant", content: reply },
  ];

  await saveHistory(sessionId, updatedHistory);

  return { reply, history: updatedHistory };
}

const tracedAnswerQuestion = traceable(answerQuestion, {
  name: "casa-alon-ask-alon",
});

// Lets the chat widget restore a visitor's previous conversation (from
// Redis) when they reopen the site, instead of always starting fresh.
export async function GET(req: NextRequest) {
  const sessionId = req.nextUrl.searchParams.get("sessionId") || "";
  const history = await loadHistory(sessionId);
  return NextResponse.json({ history });
}

export async function POST(req: NextRequest) {
  if (!process.env.GOOGLE_API_KEY) {
    return NextResponse.json(
      { error: "Server is missing GOOGLE_API_KEY." },
      { status: 500 }
    );
  }

  let body: { message?: string; sessionId?: string; history?: ChatTurn[] };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const message = body.message?.trim();
  if (!message) {
    return NextResponse.json({ error: "Missing 'message'." }, { status: 400 });
  }
  const sessionId = body.sessionId?.trim() || "";
  const clientHistory = Array.isArray(body.history)
    ? body.history.slice(-10)
    : [];

  try {
    const { reply, history } = await tracedAnswerQuestion({
      sessionId,
      message,
      clientHistory,
    });
    return NextResponse.json({ reply, history });
  } catch (err) {
    console.error("Chat route error:", err);
    return NextResponse.json(
      { error: "Something went wrong answering that." },
      { status: 500 }
    );
  }
}
