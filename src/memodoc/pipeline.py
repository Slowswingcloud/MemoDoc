"""编排层：索引流 / 问答流 / 记忆流 三条链路。"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
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
from memodoc.rag.store import DocumentRegistry, VectorStore
from memodoc.session import SessionStore
from memodoc.tagger import fallback_tags, suggest_tags

_CITE_RE = re.compile(r"\[(\d+)\]")


class Pipeline:
    def __init__(self):
        self.embedder = Embedder()
        self.vector_store = VectorStore()
        self.registry = DocumentRegistry()
        self.memory_store = MemoryStore(self.embedder)
        self.retriever = Retriever(self.vector_store, self.embedder)
        self.generator = Generator(llm)
        self.extractor = FactExtractor(llm)
        self.injector = MemoryInjector(self.memory_store)
        self.sessions = SessionStore()

    # ---------- 索引流 ----------
    def index(
        self,
        path: str,
        tenant: str | None = None,
        lifecycle: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """索引文档。

        物理层：源文件归档到 data/uploads/<tenant>/<lifecycle>/；
        逻辑层：向量库保持扁平，用 meta 里的 tenant/lifecycle/tags（虚拟标签）组织。
        """
        tenant = tenant or settings.default_tenant
        lifecycle = lifecycle or settings.default_lifecycle
        tags = tags or []

        doc = parse_file(path)
        # 未显式给标签且开启自动打标签 → LLM 建议 + 启发式兜底
        if not tags and settings.auto_tag_on_index:
            tags = suggest_tags(doc.text, self.all_tags()) or fallback_tags(doc.text)
        chunks = chunk_text(doc.text, doc.name, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            return {"doc": doc.name, "chunks": 0, "mode": "empty"}

        # 物理归档 + 逻辑标签
        dest_dir = settings.upload_dir / tenant / lifecycle
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / Path(path).name
        if Path(path).resolve() != dest_file.resolve():
            shutil.copy2(path, dest_file)
        for c in chunks:
            c.meta["source"] = str(dest_file)
            c.meta["tenant"] = tenant
            c.meta["lifecycle"] = lifecycle
            c.meta["tags"] = tags

        embeddings = self.embedder.embed([c.text for c in chunks])
        if embeddings is None:
            self.vector_store.add_chunks(chunks, None)
            mode = "keyword-fallback"
        else:
            self.vector_store.add_chunks(chunks, embeddings)
            mode = "embedding"
        # 无论向量是否可用，都用全库重建 BM25 稀疏索引（多文档下不能只重建新文档）
        all_chunks = [{"id": c["id"], "text": c["text"]} for c in self.vector_store.all_chunks()]
        self.retriever.sparse.build(all_chunks)
        self.registry.upsert(doc.name, str(dest_file), len(chunks), tenant, lifecycle, tags)
        return {"doc": doc.name, "chunks": len(chunks), "mode": mode, "tags": tags}

    def delete_doc(self, doc_name: str) -> None:
        """删除文档：向量库 + 稀疏索引 + 注册表。"""
        self.vector_store.delete_doc(doc_name)
        remaining = [{"id": c["id"], "text": c["text"]} for c in self.vector_store.all_chunks()]
        self.retriever.sparse.build(remaining)
        self.registry.remove(doc_name)

    def documents(self) -> list[dict]:
        """文档库列表：{name, source, chunks, indexed_at, tenant, lifecycle, tags}。"""
        return self.registry.all()

    def all_tags(self) -> list[str]:
        """全部文档的虚拟标签集合（供检索区间选择 / 文档库筛选）。"""
        tags: set[str] = set()
        for c in self.vector_store.all_chunks():
            tags.update(c["meta"].get("tags") or [])
        return sorted(tags)

    def set_doc_tags(self, doc_name: str, tags: list[str]) -> None:
        """修改某文档的虚拟标签（整表替换；注册表 + 该文档所有块）。"""
        self.vector_store.update_doc_tags(doc_name, tags)
        for d in self.registry.all():
            if d["name"] == doc_name:
                self.registry.upsert(
                    doc_name,
                    d.get("source", ""),
                    d.get("chunks", 0),
                    d.get("tenant", "default"),
                    d.get("lifecycle", "active"),
                    tags,
                )
                break

    def add_doc_tag(self, doc_name: str, tag: str) -> None:
        """给某文档新增一个标签（已存在则忽略）。"""
        for d in self.registry.all():
            if d["name"] == doc_name:
                tags = list(d.get("tags") or [])
                if tag and tag not in tags:
                    tags.append(tag)
                    self.set_doc_tags(doc_name, tags)
                return
        raise KeyError(f"文档不存在：{doc_name}")

    def remove_doc_tag(self, doc_name: str, tag: str) -> None:
        """删除某文档的某个标签（不存在则忽略）。"""
        for d in self.registry.all():
            if d["name"] == doc_name:
                tags = [t for t in (d.get("tags") or []) if t != tag]
                if tags != (d.get("tags") or []):
                    self.set_doc_tags(doc_name, tags)
                return
        raise KeyError(f"文档不存在：{doc_name}")

    def auto_tag(self, doc_name: str) -> list[str]:
        """自动给已索引文档打标签：读源文件 → LLM 建议（复用已有标签）→ 启发式兜底 → 写回。"""
        src = next(
            (d.get("source") for d in self.registry.all() if d["name"] == doc_name), None
        )
        if not src:
            raise KeyError(f"文档不存在：{doc_name}")
        doc = parse_file(src)
        tags = suggest_tags(doc.text, self.all_tags()) or fallback_tags(doc.text)
        self.set_doc_tags(doc_name, tags)
        return tags

    def set_doc_lifecycle(self, doc_name: str, lifecycle: str) -> None:
        """修改某文档的生命周期（注册表 + 该文档所有块）。"""
        self.vector_store.update_doc_meta(doc_name, lifecycle=lifecycle)
        for d in self.registry.all():
            if d["name"] == doc_name:
                self.registry.upsert(
                    doc_name,
                    d.get("source", ""),
                    d.get("chunks", 0),
                    d.get("tenant", "default"),
                    lifecycle,
                    d.get("tags", []),
                )
                break

    def reindex(self, doc_name: str) -> dict:
        """按注册表里的源路径重新索引某文档（保留原租户/生命周期/标签）。"""
        for d in self.registry.all():
            if d["name"] == doc_name:
                return self.index(
                    d["source"],
                    tenant=d.get("tenant"),
                    lifecycle=d.get("lifecycle"),
                    tags=d.get("tags"),
                )
        raise KeyError(f"文档不存在：{doc_name}")

    # ---------- 问答流 ----------
    def answer_stream(
        self,
        session_id: str,
        question: str,
        use_memory: bool = True,
        user_id: str = "default",
        tenant: str | None = None,
        lifecycle: str | None = None,
        tags: list[str] | None = None,
    ) -> Iterator[tuple[str, list[Retrieved]]]:
        mem_facts = self.injector.facts(question, user_id) if use_memory else []
        memories = self.injector.format(mem_facts)
        # 记忆增强检索：把相关记忆拼进查询，提升命中（如"我是大一新生"→ 入社条件块）
        retrieval_query = (
            "，".join(f["content"] for f in mem_facts) + "。" + question if mem_facts else question
        )
        retrieved = self.retriever.retrieve(
            retrieval_query, route_hint=question,
            tenant=tenant, lifecycle=lifecycle, tags=tags,
        )
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
        retrieved: list[Retrieved] | None = None,
        tenant: str | None = None,
        lifecycle: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        mem_facts = self.injector.facts(question, user_id) if use_memory else []
        memories = self.injector.format(mem_facts)
        if retrieved is None:
            retrieval_query = (
                "，".join(f["content"] for f in mem_facts) + "。" + question if mem_facts else question
            )
            retrieved = self.retriever.retrieve(
                retrieval_query, route_hint=question,
                tenant=tenant, lifecycle=lifecycle, tags=tags,
            )
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

    # ---------- 引用核查（对齐 Kotaemon 的 CitationPipeline）----------
    def check_citations(self, answer: str, retrieved: list[Retrieved]) -> dict[int, str]:
        """逐条核查回答中 [n] 引用是否被对应片段支持。

        返回 {n: "supported" | "unsupported" | "unknown"}；无引用时返回空 dict。
        """
        cited = sorted({int(m) for m in _CITE_RE.findall(answer)})
        if not cited:
            return {}
        by_index = {r.index: r for r in retrieved}
        items = [(n, by_index[n]) for n in cited if n in by_index]
        if not items:
            return {}
        system = (
            "你是引用核查器。判断回答中每个 [n] 引用的内容是否确实由对应的文档片段支持。\n"
            "规则：片段中没有的信息，该引用必须标为 unsupported；片段明确支持则标 supported。\n"
            "只输出 JSON 对象，形如 {\"1\": \"supported\", \"2\": \"unsupported\"}，不要任何解释。"
        )
        body = ["回答：", answer, "", "文档片段："]
        for n, r in items:
            body.append(f"[{n}] {r.text}")
        data = self.generator.llm.chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": "\n".join(body)},
            ]
        )
        result: dict[int, str] = {}
        if isinstance(data, dict):
            for n, _ in items:
                v = data.get(str(n)) or data.get(n)
                result[n] = v if v in ("supported", "unsupported") else "unknown"
        return result
