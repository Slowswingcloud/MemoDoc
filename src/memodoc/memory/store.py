"""记忆存储：向量库 + 去重 + 同属性冲突更新。"""
from __future__ import annotations

import time
import uuid

from memodoc.config import settings
from memodoc.rag.embedder import QUERY_INSTRUCTION, Embedder
from memodoc.rag.store import JsonVectorStore


class MemoryStore:
    def __init__(self, embedder: Embedder):
        self.embedder = embedder
        self._store = JsonVectorStore(settings.store_dir / "memories.json")

    def add(self, fact: dict, user_id: str = "default") -> bool:
        """返回 True 表示有新事实被记录或更新，False 表示去重跳过。"""
        content = fact["content"]
        emb = self.embedder.embed([content])
        if emb is None:
            # 无 embedding 的降级模式：做精确内容去重
            if any(it["text"] == content for it in self._store.all({"user_id": user_id})):
                return False
            self._insert(fact, user_id, None)
            return True

        res = self._store.query(emb[0], 1, {"user_id": user_id})
        if res:
            sim = 1.0 - res[0]["distance"]
            meta = res[0]["meta"]
            if sim >= settings.memory_sim_threshold:
                return False  # 高度相似：去重
            if meta.get("subject") == fact["subject"] and meta.get("type") == fact["type"] and sim >= 0.6:
                self._store.delete_ids([res[0]["id"]])  # 同属性冲突：替换为新事实
        self._insert(fact, user_id, emb[0])
        return True

    def _insert(self, fact: dict, user_id: str, embedding: list[float] | None) -> None:
        fid = f"mem-{uuid.uuid4().hex[:12]}"
        meta = {
            "type": fact["type"],
            "subject": fact["subject"],
            "user_id": user_id,
            "ts": time.time(),
        }
        self._store.add(
            [fid],
            [fact["content"]],
            [meta],
            [embedding] if embedding is not None else None,
        )

    def search(self, query: str, top_k: int | None = None, user_id: str = "default") -> list[dict]:
        top_k = top_k or settings.memory_top_k
        emb = self.embedder.embed([QUERY_INSTRUCTION + query])
        if emb is None:
            return self.all(user_id)[:top_k]
        res = self._store.query(emb[0], top_k, {"user_id": user_id})
        return [{"content": r["text"], "meta": r["meta"]} for r in res]

    def all(self, user_id: str = "default") -> list[dict]:
        items = [{"content": it["text"], "meta": it["meta"]} for it in self._store.all({"user_id": user_id})]
        items.sort(key=lambda x: x["meta"].get("ts", 0), reverse=True)
        return items

    def count(self, user_id: str = "default") -> int:
        return self._store.count({"user_id": user_id})

    def clear(self, user_id: str = "default") -> None:
        self._store.delete_where(user_id=user_id)
