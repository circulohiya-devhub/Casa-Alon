import { NextRequest, NextResponse } from "next/server";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import {
  HumanMessage,
  AIMessage,
  SystemMessage,
} from "@langchain/core/messages";
import { retrieveContext } from "@/lib/rag";

// LangChain's Google GenAI packages need Node APIs, so this can't run on
// the Edge runtime.
export const runtime = "nodejs";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

const SYSTEM_PROMPT = `You are "Ask Alon," the guest-facing assistant for Casa Alon, a small
boutique hotel in Puerto Princesa, Palawan.

Answer only using the CONTEXT provided below plus the conversation so far.
If the answer isn't in the context, say you're not sure and suggest the
guest email stay@casaalon.com — never invent rates, dates, or policies.
Keep answers short, warm, and specific. You are not able to make or modify
a booking yourself; direct booking requests to the contact email or phone
number.`;

export async function POST(req: NextRequest) {
  if (!process.env.GOOGLE_API_KEY) {
    return NextResponse.json(
      { error: "Server is missing GOOGLE_API_KEY." },
      { status: 500 }
    );
  }

  let body: { message?: string; history?: ChatMessage[] };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const message = body.message?.trim();
  if (!message) {
    return NextResponse.json({ error: "Missing 'message'." }, { status: 400 });
  }
  const history = Array.isArray(body.history) ? body.history.slice(-10) : [];

  try {
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
      ...history.map((turn) =>
        turn.role === "user"
          ? new HumanMessage(turn.content)
          : new AIMessage(turn.content)
      ),
      new HumanMessage(message),
    ];

    const response = await model.invoke(messages);

    return NextResponse.json({
      reply: response.content,
    });
  } catch (err) {
    console.error("Chat route error:", err);
    return NextResponse.json(
      { error: "Something went wrong answering that." },
      { status: 500 }
    );
  }
}
