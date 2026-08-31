"""检索：向量 Top-K + 稀疏 BM25 混合融合 + 跨语言双语检索 + 交叉编码器重排。

对齐 Kotaemon 的 hybrid retrieval 设计，并扩展：
- 跨语言：中文查询先由 LLM 翻译成英文，中英双语各自检索一次后按 id 合并候选，
  再交给多语言重排器精排（解决"中文问英文论文"场景）；
- 检索支持按 doc_name 限定域（供文档路由使用）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from memodoc.config import settings
from memodoc.llm.openai_compat import llm
from memodoc.rag.embedder import QUERY_INSTRUCTION, Embedder
from memodoc.rag.reranker import Reranker
from memodoc.rag.sparse import BM25Index
from memodoc.rag.store import VectorStore

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


@dataclass
class Retrieved:
    id: str = ""
    index: int = 0  # 引用编号，1..k，与生成 prompt 中的 [n] 一致
    text: str = ""
    doc_name: str = ""
    section: str = ""
    score: float = 0.0
    source: str = ""  # 源文件路径（供前端点击打开）


class Retriever:
    def __init__(self, store: VectorStore, embedder: Embedder):
        self.store = store
        self.embedder = embedder
        self.sparse = BM25Index(settings.store_dir / "sparse.json")
        self.reranker = Reranker()
        self.llm = llm

    def rebuild_sparse(self, chunks) -> None:
        """索引后同步重建 BM25 倒排索引。chunks: list[Chunk]"""
        self.sparse.build([{"id": c.id, "text": c.text} for c in chunks])

    def _ensure_sparse(self) -> None:
        if self.sparse.is_empty():
            self.sparse.build(
                [{"id": c["id"], "text": c["text"]} for c in self.store.all_chunks()]
            )

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        use_rerank: bool | None = None,
        doc_name: str | None = None,
        tenant: str | None = None,
        lifecycle: str | None = None,
        tags: list[str] | None = None,
        route_hint: str | None = None,
    ) -> list[Retrieved]:
        top_k = top_k or settings.top_k
        candidates_n = max(settings.retrieve_candidates, top_k)
        use_rerank = settings.use_rerank if use_rerank is None else use_rerank

        # 文档路由：查询提及文档标题时，先限定到该文档域内检索。
        # 未显式传 route_hint 时自动对查询本身做路由（管道传原始问题，避开记忆拼贴干扰）。
        if doc_name is None:
            doc_name = self._route_doc(route_hint or query)

        candidates = self._retrieve_variants(query, candidates_n, doc_name, tenant, lifecycle, tags)
        if doc_name and not candidates:
            # 路由落空（标题匹配错）→ 回退全局检索
            candidates = self._retrieve_variants(query, candidates_n, None, tenant, lifecycle, tags)

        if not candidates:
            return []
        if use_rerank:
            candidates = self.reranker.rerank(query, candidates, top_k)
        else:
            candidates = candidates[:top_k]
        # LLM 重排（Kotaemon LLMScoring 思路）：cross-encoder 之后再让 LLM 精排 top-8
        if settings.use_llm_rerank and candidates:
            candidates = self._llm_rerank(query, candidates, top_k)
        for i, r in enumerate(candidates, 1):
            r.index = i
        return candidates

    def _llm_rerank(self, query: str, candidates: list[Retrieved], top_k: int) -> list[Retrieved]:
        """用 LLM 对候选片段按相关性排序（跨语言场景比 cross-encoder 更稳，代价是多次 LLM 调用）。"""
        if not self.llm.configured:
            return candidates[:top_k]
        cands = candidates[: max(top_k * 2, 8)]
        body = "\n".join(f"[{i + 1}] {c.text[:200]}" for i, c in enumerate(cands))
        prompt = (
            "根据查询的相关性，把以下文档片段从最相关到最不相关排序。"
            "只输出片段编号数组（如 [3,1,2]），不要解释。\n\n"
            f"查询：{query}\n\n{body}"
        )
        try:
            data = self.llm.chat_json([{"role": "user", "content": prompt}])
        except Exception:
            return candidates[:top_k]
        if not isinstance(data, list) or not data:
            return candidates[:top_k]
        order = [int(x) for x in data if str(x).lstrip("-").isdigit()]
        seen = set()
        ordered: list[Retrieved] = []
        for idx in order:
            if 1 <= idx <= len(cands) and idx not in seen:
                seen.add(idx)
                ordered.append(cands[idx - 1])
        ordered += [c for i, c in enumerate(cands, 1) if i not in seen]
        return ordered[:top_k]

    def _retrieve_variants(
        self,
        query: str,
        n: int,
        doc_name: str | None,
        tenant: str | None,
        lifecycle: str | None,
        tags: list[str] | None,
    ) -> list[Retrieved]:
        """跨语言：含中文的查询翻译成英文，双语各自检索后按 id 合并候选（保留更高分）。"""
        variants = [query]
        if settings.enable_query_translation:
            en = self._translate_to_en(query)
            if en and en != query:
                variants.append(en)

        merged: dict[str, Retrieved] = {}
        for q in variants:
            for r in self._retrieve_one(q, n, doc_name, tenant, lifecycle, tags):
                if r.id not in merged or r.score > merged[r.id].score:
                    merged[r.id] = r
        return sorted(merged.values(), key=lambda x: -x.score)

    def _route_doc(self, query: str) -> str | None:
        """根据查询中的文档标题片段，返回最可能的目标文档名（无匹配返回 None）。

        三级匹配：完整标题子串 → 连字符缩写（agent-os）→ ASCII 词重叠（≥2 词）。
        """
        docs = self.store.indexed_docs()
        if not docs:
            return None
        q = query.lower()
        # 1) 完整标题（含中文文档名）出现在查询中
        for d in docs:
            dl = d.lower()
            if len(dl) >= 8 and dl in q:
                return d
        # 2) 连字符缩写精确命中标题（如 "Agent-OS" → "agent-os" in "agent operating systems agent-os…"）
        for tok in re.findall(r"[a-z0-9]+-[a-z0-9]+", q):
            for d in docs:
                if tok in d.lower():
                    return d
        # 2.5) 唯一词路由：查询中的词只出现在某一篇文档标题里（如 mem1 / memmachine）→ 直接路由
        q_tokens = {t for t in re.findall(r"[a-z0-9]+", q) if len(t) >= 2}
        for t in q_tokens:
            matches = [d for d in docs if t in d.lower()]
            if len(matches) == 1:
                return matches[0]
        # 3) ASCII 词重叠计分，≥2 词才算路由
        best, best_score = None, 0
        for d in docs:
            d_tokens = {t for t in re.findall(r"[a-z0-9]+", d.lower()) if len(t) >= 2}
            score = len(q_tokens & d_tokens)
            if score > best_score:
                best, best_score = d, score
        return best if best_score >= 2 else None

    def _retrieve_one(
        self,
        query: str,
        n: int,
        doc_name: str | None,
        tenant: str | None = None,
        lifecycle: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Retrieved]:
        """单个查询变体（原语或英文翻译）的 向量+BM25 融合召回。"""
        dense = self._dense(query, n, doc_name, tenant, lifecycle, tags)
        self._ensure_sparse()
        sparse = self._sparse(query, n, doc_name, tenant, lifecycle, tags)
        if dense and sparse:
            return _fuse(dense, sparse, settings.hybrid_weight)
        return dense or sparse

    def _translate_to_en(self, query: str) -> str | None:
        """中文查询 → 英文；失败时静默降级为单语检索。"""
        if not _CJK_RE.search(query):
            return None
        try:
            prompt = (
                "Translate the following Chinese search query into English. "
                "Output ONLY the English translation, no explanation.\n\n" + query
            )
            out = self.llm.chat(
                [{"role": "user", "content": prompt}], temperature=0.0
            ).strip()
            return out or None
        except Exception:
            return None

    # ---------- 两条召回通道 ----------
    def _dense(
        self,
        query: str,
        n: int,
        doc_name: str | None = None,
        tenant: str | None = None,
        lifecycle: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Retrieved]:
        emb = self.embedder.embed([QUERY_INSTRUCTION + query])
        if emb is None:
            return []
        out = []
        for i, r in enumerate(self.store.query(emb[0], n, doc_name, tenant, lifecycle, tags)):
            out.append(
                Retrieved(
                    id=r["id"],
                    index=i + 1,
                    text=r["text"],
                    doc_name=r["meta"].get("doc_name", ""),
                    section=r["meta"].get("section", ""),
                    score=1.0 - r["distance"],
                    source=r["meta"].get("source", ""),
                )
            )
        return out

    def _sparse(
        self,
        query: str,
        n: int,
        doc_name: str | None = None,
        tenant: str | None = None,
        lifecycle: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Retrieved]:
        if self.sparse.is_empty():
            return []
        ranked = self.sparse.search(query, n)
        if not ranked:
            return []
        all_chunks = {c["id"]: c for c in self.store.all_chunks(doc_name, tenant, lifecycle, tags)}
        out = []
        for cid, score in ranked:
            c = all_chunks.get(cid)
            if c is None:
                continue
            out.append(
                Retrieved(
                    id=cid,
                    index=len(out) + 1,
                    text=c["text"],
                    doc_name=c["meta"].get("doc_name", ""),
                    section=c["meta"].get("section", ""),
                    score=score,
                    source=c["meta"].get("source", ""),
                )
            )
        return out


def _fuse(dense: list[Retrieved], sparse: list[Retrieved], w: float) -> list[Retrieved]:
    """加权融合：各自 min-max 归一化到 [0,1]，再 final = w*dense + (1-w)*sparse。"""
    d_min = min(r.score for r in dense)
    d_max = max(r.score for r in dense)
    s_min = min(r.score for r in sparse)
    s_max = max(r.score for r in sparse)

    def norm(v: float, lo: float, hi: float) -> float:
        return (v - lo) / (hi - lo) if hi > lo else 1.0

    merged: dict[str, Retrieved] = {}
    for r in dense:
        merged[r.id] = Retrieved(
            id=r.id, text=r.text, doc_name=r.doc_name, section=r.section,
            score=w * norm(r.score, d_min, d_max), source=r.source,
        )
    for r in sparse:
        if r.id in merged:
            merged[r.id].score += (1 - w) * norm(r.score, s_min, s_max)
        else:
            merged[r.id] = Retrieved(
                id=r.id, text=r.text, doc_name=r.doc_name, section=r.section,
                score=(1 - w) * norm(r.score, s_min, s_max), source=r.source,
            )
    return sorted(merged.values(), key=lambda x: -x.score)
