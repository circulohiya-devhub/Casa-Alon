import { Document } from "@langchain/core/documents";
import { GoogleGenerativeAIEmbeddings } from "@langchain/google-genai";
import { MemoryVectorStore } from "langchain/vectorstores/memory";
import { KNOWLEDGE_BASE } from "./knowledge";

/**
 * This is intentionally the simplest possible RAG setup: a handful of
 * documents embedded into an in-memory vector store at cold start.
 *
 * It's a fine starting point for a small, mostly-static knowledge base,
 * but it has real limits worth knowing about before you rely on it:
 *  - every cold start re-embeds all documents (fine for ~10 docs, not
 *    for hundreds)
 *  - nothing is shared across serverless instances
 *  - there's no incremental update story if the knowledge base changes
 *    often
 *
 * When you outgrow it, swap MemoryVectorStore for a persistent/hosted
 * vector store (e.g. the Vercel Postgres/pgvector integration, Pinecone,
 * or Supabase) and keep everything else in this file the same — only the
 * store changes, not the retrieval call in route.ts.
 */

let vectorStorePromise: Promise<MemoryVectorStore> | null = null;

function getEmbeddings() {
  return new GoogleGenerativeAIEmbeddings({
    apiKey: process.env.GOOGLE_API_KEY,
    model: "text-embedding-004",
  });
}

async function buildVectorStore(): Promise<MemoryVectorStore> {
  const docs = KNOWLEDGE_BASE.map(
    (entry) =>
      new Document({
        pageContent: entry.content,
        metadata: { id: entry.id, topic: entry.topic },
      })
  );

  return MemoryVectorStore.fromDocuments(docs, getEmbeddings());
}

function getVectorStore(): Promise<MemoryVectorStore> {
  if (!vectorStorePromise) {
    vectorStorePromise = buildVectorStore();
  }
  return vectorStorePromise;
}

export async function retrieveContext(
  query: string,
  k = 4
): Promise<Document[]> {
  const store = await getVectorStore();
  return store.similaritySearch(query, k);
}
