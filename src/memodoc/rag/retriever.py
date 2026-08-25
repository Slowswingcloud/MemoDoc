"""向量检索 Top-K；embedding 不可用时回退到字符 bigram 关键词打分。"""
from __future__ import annotations

import re
from dataclasses import dataclass

from memodoc.config import settings
from memodoc.rag.embedder import QUERY_INSTRUCTION, Embedder
from memodoc.rag.store import VectorStore


@dataclass
class Retrieved:
    index: int  # 引用编号，从 1 开始，与生成 prompt 中的 [n] 一致
    text: str
    doc_name: str
    section: str
    score: float


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


class Retriever:
    def __init__(self, store: VectorStore, embedder: Embedder):
        self.store = store
        self.embedder = embedder

    def retrieve(self, query: str, top_k: int | None = None) -> list[Retrieved]:
        top_k = top_k or settings.top_k
        emb = self.embedder.embed([QUERY_INSTRUCTION + query])
        if emb is not None:
            results = self.store.query(emb[0], top_k)
            return [
                Retrieved(
                    index=i + 1,
                    text=r["text"],
                    doc_name=r["meta"].get("doc_name", ""),
                    section=r["meta"].get("section", ""),
                    score=1.0 - r["distance"],
                )
                for i, r in enumerate(results)
            ]
        return self._keyword(query, top_k)

    def _keyword(self, query: str, top_k: int) -> list[Retrieved]:
        q_grams = _bigrams(query)
        scored: list[tuple[int, dict]] = []
        for c in self.store.all_chunks():
            overlap = len(q_grams & _bigrams(c["text"]))
            if overlap:
                scored.append((overlap, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            Retrieved(
                index=i + 1,
                text=c["text"],
                doc_name=c["meta"].get("doc_name", ""),
                section=c["meta"].get("section", ""),
                score=float(s),
            )
            for i, (s, c) in enumerate(scored[:top_k])
        ]


def _bigrams(text: str) -> set[str]:
    text = re.sub(r"\s+", "", text)
    grams: set[str] = set()
    for i in range(len(text) - 1):
        a, b = text[i], text[i + 1]
        if _CJK_RE.match(a) and _CJK_RE.match(b):
            grams.add(a + b)
    for w in re.findall(r"[A-Za-z0-9]{2,}", text):
        grams.add(w.lower())
    return grams
