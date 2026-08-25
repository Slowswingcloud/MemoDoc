"""编排层：索引流 / 问答流 / 记忆流 三条链路。"""
from __future__ import annotations

from typing import Iterator

from memodoc.config import settings
from memodoc.llm.openai_compat import llm
from memodoc.memory.extractor import FactExtractor
from memodoc.memory.injector import MemoryInjector
from memodoc.memory.store import MemoryStore
from memodoc.rag.chunker import chunk_text
from memodoc.rag.embedder import Embedder
from memodoc.rag.generator import Generator
from memodoc.rag.parser import parse_file
from memodoc.rag.retriever import Retrieved, Retriever
from memodoc.rag.store import VectorStore
from memodoc.session import SessionStore


class Pipeline:
    def __init__(self):
        self.embedder = Embedder()
        self.vector_store = VectorStore()
        self.memory_store = MemoryStore(self.embedder)
        self.retriever = Retriever(self.vector_store, self.embedder)
        self.generator = Generator(llm)
        self.extractor = FactExtractor(llm)
        self.injector = MemoryInjector(self.memory_store)
        self.sessions = SessionStore()

    # ---------- 索引流 ----------
    def index(self, path: str) -> dict:
        doc = parse_file(path)
        chunks = chunk_text(doc.text, doc.name, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            return {"doc": doc.name, "chunks": 0, "mode": "empty"}
        embeddings = self.embedder.embed([c.text for c in chunks])
        if embeddings is None:
            self.vector_store.add_chunks(chunks, None)
            return {"doc": doc.name, "chunks": len(chunks), "mode": "keyword-fallback"}
        self.vector_store.add_chunks(chunks, embeddings)
        return {"doc": doc.name, "chunks": len(chunks), "mode": "embedding"}

    # ---------- 问答流 ----------
    def answer_stream(
        self,
        session_id: str,
        question: str,
        use_memory: bool = True,
        user_id: str = "default",
    ) -> Iterator[tuple[str, list[Retrieved]]]:
        mem_facts = self.injector.facts(question, user_id) if use_memory else []
        memories = self.injector.format(mem_facts)
        # 记忆增强检索：把相关记忆拼进查询，提升命中（如"我是大一新生"→ 入社条件块）
        retrieval_query = (
            "，".join(f["content"] for f in mem_facts) + "。" + question if mem_facts else question
        )
        retrieved = self.retriever.retrieve(retrieval_query)
        history = self.sessions.recent(session_id)
        messages = self.generator.build_messages(question, retrieved, memories, history)

        full = ""
        for delta in self.generator.stream(messages):
            full += delta
            yield delta, retrieved

        self.sessions.append(session_id, "user", question)
        self.sessions.append(session_id, "assistant", full)

        # ---------- 记忆流（每轮后，仅在使用记忆时）----------
        if use_memory:
            try:
                for fact in self.extractor.extract(question, full):
                    self.memory_store.add(fact, user_id)
            except Exception:
                pass

    def answer(
        self,
        session_id: str,
        question: str,
        use_memory: bool = False,
        user_id: str = "default",
    ) -> str:
        mem_facts = self.injector.facts(question, user_id) if use_memory else []
        memories = self.injector.format(mem_facts)
        retrieval_query = (
            "，".join(f["content"] for f in mem_facts) + "。" + question if mem_facts else question
        )
        retrieved = self.retriever.retrieve(retrieval_query)
        history = self.sessions.recent(session_id)
        messages = self.generator.build_messages(question, retrieved, memories, history)
        return self.generator.complete(messages)

    # ---------- 记忆管理 ----------
    def list_memories(self, user_id: str = "default") -> list[dict]:
        return self.memory_store.all(user_id)

    def clear_memories(self, user_id: str = "default") -> None:
        self.memory_store.clear(user_id)

    def reset_session(self, session_id: str) -> None:
        self.sessions.reset(session_id)

    def indexed_docs(self) -> list[str]:
        return self.vector_store.indexed_docs()
