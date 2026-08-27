"""自研轻量向量存储：numpy 余弦检索 + JSON 持久化。

设计取舍：本机无 MSVC 构建工具，ChromaDB 依赖的 chroma-hnswlib 无法编译；
演示规模（数百块）下 O(n) 精确检索毫秒级完成，JSON 存储可审计、零原生依赖。
接口与 ChromaDB 风格对齐，后续可无缝替换为真正的向量数据库。
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import numpy as np

from memodoc.config import settings
from memodoc.rag.chunker import Chunk


class DocumentRegistry:
    """文档注册表：doc_name → {source, chunks, indexed_at}，JSON 持久化（供文档库查看）。"""

    def __init__(self, path: Path | None = None):
        self.path = path or settings.store_dir / "documents.json"
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")

    def upsert(
        self,
        doc_name: str,
        source: str,
        chunks: int,
        tenant: str = "default",
        lifecycle: str = "active",
        tags: list | None = None,
    ) -> None:
        self._data[doc_name] = {
            "source": source,
            "chunks": chunks,
            "indexed_at": time.time(),
            "tenant": tenant,
            "lifecycle": lifecycle,
            "tags": tags or [],
        }
        self._save()

    def remove(self, doc_name: str) -> None:
        self._data.pop(doc_name, None)
        self._save()

    def all(self) -> list[dict]:
        out = []
        for name, info in sorted(
            self._data.items(), key=lambda kv: kv[1].get("indexed_at", 0), reverse=True
        ):
            out.append({"name": name, **info})
        return out


class JsonVectorStore:
    """通用 JSON 向量库：items = [{id, text, meta, embedding}]。"""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._items: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            self._items = json.loads(self.path.read_text(encoding="utf-8"))
            # 旧数据迁移：补齐逻辑空间字段（tenant/lifecycle/tags），保持扁平可查
            changed = False
            for it in self._items:
                meta = it.get("meta") or {}
                for k, v in (("tenant", "default"), ("lifecycle", "active"), ("tags", [])):
                    if k not in meta:
                        meta[k] = v
                        changed = True
                it["meta"] = meta
            if changed:
                self._save()
        except Exception:
            self._items = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._items, ensure_ascii=False), encoding="utf-8")

    def add(self, ids, texts, metas, embeddings) -> None:
        with self._lock:
            drop = set(ids)
            self._items = [it for it in self._items if it["id"] not in drop]
            for i in range(len(ids)):
                self._items.append(
                    {
                        "id": ids[i],
                        "text": texts[i],
                        "meta": metas[i],
                        "embedding": embeddings[i] if embeddings is not None else None,
                    }
                )
            self._save()

    def delete_ids(self, ids) -> None:
        drop = set(ids)
        with self._lock:
            self._items = [it for it in self._items if it["id"] not in drop]
            self._save()

    def delete_where(self, **kv) -> None:
        with self._lock:
            self._items = [
                it
                for it in self._items
                if not all(it["meta"].get(k) == v for k, v in kv.items())
            ]
            self._save()

    def update_meta_where(self, fields: dict, where: dict) -> None:
        """按 where 精确匹配，更新匹配项的 meta 字段（如改虚拟标签）。"""
        with self._lock:
            for it in self._items:
                if all(it["meta"].get(k) == v for k, v in where.items()):
                    it["meta"].update(fields)
            self._save()

    def query(
        self,
        embedding: list[float],
        top_k: int,
        where: dict | None = None,
        tag_filter: list[str] | None = None,
    ) -> list[dict]:
        emb = np.asarray(embedding, dtype="float32")
        rows = [
            it
            for it in self._items
            if it.get("embedding") is not None
            and (where is None or all(it["meta"].get(k) == v for k, v in where.items()))
            and (tag_filter is None or any(t in (it["meta"].get("tags") or []) for t in tag_filter))
        ]
        if not rows:
            return []
        mat = np.stack([np.asarray(r["embedding"], dtype="float32") for r in rows])
        sims = mat @ emb  # embedding 已归一化，点积即余弦相似度
        order = np.argsort(-sims)[:top_k]
        return [
            {
                "id": rows[int(i)]["id"],
                "text": rows[int(i)]["text"],
                "meta": rows[int(i)]["meta"],
                "distance": 1.0 - float(sims[int(i)]),
            }
            for i in order
        ]

    def all(self, where: dict | None = None, tag_filter: list[str] | None = None) -> list[dict]:
        return [
            {"id": it["id"], "text": it["text"], "meta": it["meta"]}
            for it in self._items
            if (where is None or all(it["meta"].get(k) == v for k, v in where.items()))
            and (tag_filter is None or any(t in (it["meta"].get("tags") or []) for t in tag_filter))
        ]

    def count(self, where: dict | None = None) -> int:
        return len(self.all(where))


class VectorStore:
    """文档块向量库。"""

    def __init__(self):
        self._store = JsonVectorStore(settings.store_dir / "docs.json")

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]] | None) -> None:
        for dn in {c.doc_name for c in chunks}:
            self._store.delete_where(doc_name=dn)
        self._store.add(
            ids=[c.id for c in chunks],
            texts=[c.text for c in chunks],
            metas=[
                {"doc_name": c.doc_name, "section": c.section_path, **c.meta}
                for c in chunks
            ],
            embeddings=embeddings,
        )

    def delete_doc(self, doc_name: str) -> None:
        self._store.delete_where(doc_name=doc_name)

    def update_doc_tags(self, doc_name: str, tags: list[str]) -> None:
        """更新某文档所有块的虚拟标签（逻辑层标签管理）。"""
        self._store.update_meta_where({"tags": tags}, {"doc_name": doc_name})

    def update_doc_meta(self, doc_name: str, **fields) -> None:
        """更新某文档所有块的任意 meta 字段（如 lifecycle）。"""
        self._store.update_meta_where(fields, {"doc_name": doc_name})

    def query(
        self,
        embedding: list[float],
        top_k: int,
        doc_name: str | None = None,
        tenant: str | None = None,
        lifecycle: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict]:
        where: dict = {}
        if doc_name:
            where["doc_name"] = doc_name
        if tenant:
            where["tenant"] = tenant
        if lifecycle:
            where["lifecycle"] = lifecycle
        return self._store.query(embedding, top_k, where or None, tags)

    def all_chunks(
        self,
        doc_name: str | None = None,
        tenant: str | None = None,
        lifecycle: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict]:
        where: dict = {}
        if doc_name:
            where["doc_name"] = doc_name
        if tenant:
            where["tenant"] = tenant
        if lifecycle:
            where["lifecycle"] = lifecycle
        return self._store.all(where or None, tags)

    def indexed_docs(self) -> list[str]:
        docs = {it["meta"].get("doc_name") for it in self._store.all() if it["meta"].get("doc_name")}
        return sorted(docs)
