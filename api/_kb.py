"""
Live Google Doc knowledge base — ported from the original rag.py almost
unchanged. Re-checked every REFRESH_SECONDS; re-embedded only when the Doc's
text actually changed (tracked by a content hash).

This is safe to keep as in-process, module-level state even on Vercel: the
worst a cold start costs is one extra fetch-and-embed of the Doc (a second
or two), never a wrong or stale answer, since `refresh()` is always called
before `search()`.
"""
import hashlib
import logging
import os
import threading
import time

import requests
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

log = logging.getLogger("kb")

HOTEL_NAME = "Casa Alon Hotel"


class KnowledgeBase:
    def __init__(self, doc_id: str, refresh_seconds: int, embeddings):
        self.url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
        self.refresh_seconds = refresh_seconds
        self.embeddings = embeddings
        self.splitter = RecursiveCharacterTextSplitter.from_language(
            Language.MARKDOWN, chunk_size=800, chunk_overlap=100
        )
        self.store: InMemoryVectorStore | None = None
        self._hash: str | None = None
        self._last_check = 0.0
        self._lock = threading.Lock()

    def refresh(self, force: bool = False) -> bool:
        """Re-download the Doc; rebuild the vector store only if the text changed.
        Returns True if the knowledge base was reloaded."""
        with self._lock:
            now = time.time()
            if not force and self.store is not None and now - self._last_check < self.refresh_seconds:
                return False
            self._last_check = now

            try:
                resp = requests.get(self.url, timeout=20)
                resp.raise_for_status()
            except requests.RequestException as e:
                if self.store is None:
                    raise
                log.warning("Could not reach the Google Doc, keeping the previous version: %s", e)
                return False

            resp.encoding = "utf-8"  # keeps peso signs and other symbols intact
            text = resp.text.lstrip("\ufeff")

            if "<html" in text[:300].lower():
                msg = "Google returned a login page. Is the Doc shared as 'Anyone with the link: Viewer'?"
                if self.store is None:
                    raise RuntimeError(msg)
                log.warning("%s Keeping the previous version.", msg)
                return False

            new_hash = hashlib.sha256(text.encode()).hexdigest()
            if new_hash == self._hash:
                return False

            splits = self.splitter.split_documents(
                [Document(page_content=text, metadata={"source": f"{HOTEL_NAME} KB (Google Doc)"})]
            )
            store = InMemoryVectorStore(self.embeddings)
            store.add_documents(splits)
            self.store, self._hash = store, new_hash
            log.info("Knowledge base reloaded: %d chunks", len(splits))
            return True

    def search(self, query: str, k: int = 4):
        self.refresh()
        return self.store.similarity_search(query, k=k)


EMBED_MODEL = os.getenv("EMBED_MODEL", "models/gemini-embedding-001")
GDOC_ID = os.environ["GDOC_ID"]
REFRESH_SECONDS = int(os.getenv("REFRESH_SECONDS", "60"))

embeddings = GoogleGenerativeAIEmbeddings(model=EMBED_MODEL)
kb = KnowledgeBase(GDOC_ID, REFRESH_SECONDS, embeddings)
