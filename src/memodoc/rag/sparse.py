"""稀疏检索：手写 BM25（jieba 分词），对齐 Kotaemon 的 sparse retrieval 思路。

BM25 公式：score(d,q) = Σ idf(t) * f(t,d)*(k1+1) / (f(t,d) + k1*(1 - b + b*|d|/avgdl))
倒排索引以 JSON 持久化（data/store/sparse.json），随文档索引同步重建。
"""
from __future__ import annotations

import json
import math
import re
import threading
from pathlib import Path

import jieba

_ASCII_RE = re.compile(r"[A-Za-z0-9]+")
_CJK_RE = re.compile(r"^[\u4e00-\u9fff]+$")
_K1 = 1.5
_B = 0.75
# 分词器版本：改动分词逻辑后旧索引自动重建
_TOKENIZER_VERSION = 2


def _is_english(text: str) -> bool:
    """按非空白字符中 ASCII 字母占比判断语言（英文文档/查询走英文分词）。"""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    ascii_letters = sum(1 for c in chars if c.isascii() and c.isalpha())
    return ascii_letters / len(chars) > 0.5


def tokenize(text: str) -> list[str]:
    """跨语言分词：英文按词切分（统一小写、去连字符），中文走 jieba。

    这是"中文问英文论文"能命中 BM25 的关键——英文文本不再被 jieba 切碎。
    """
    tokens: list[str] = []
    if _is_english(text):
        for w in _ASCII_RE.findall(text):
            if len(w) >= 2:
                tokens.append(w.lower())
        return tokens
    for s in jieba.lcut(text):
        s = s.strip()
        if not s:
            continue
        if _CJK_RE.match(s):
            tokens.append(s)
        else:
            for w in _ASCII_RE.findall(s):
                if len(w) >= 2:
                    tokens.append(w.lower())
    return tokens


class BM25Index:
    """倒排索引 + BM25 打分。"""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.corpus_size = 0
        self.avgdl = 1.0
        self.doc_len: dict[str, int] = {}
        self.tf: dict[str, dict[str, int]] = {}
        self.df: dict[str, int] = {}
        self._load()

    # ---------- 构建 ----------
    def build(self, chunks: list[dict]) -> None:
        """chunks: [{"id": ..., "text": ...}]"""
        with self._lock:
            self.corpus_size = len(chunks)
            self.doc_len = {}
            self.tf = {}
            self.df = {}
            for c in chunks:
                toks = tokenize(c["text"])
                cid = c["id"]
                self.doc_len[cid] = len(toks)
                cnt: dict[str, int] = {}
                for t in toks:
                    cnt[t] = cnt.get(t, 0) + 1
                self.tf[cid] = cnt
                for t in set(cnt):
                    self.df[t] = self.df.get(t, 0) + 1
            self.avgdl = sum(self.doc_len.values()) / max(self.corpus_size, 1)
            self._save()

    def is_empty(self) -> bool:
        return self.corpus_size == 0

    # ---------- 检索 ----------
    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        """返回 [(chunk_id, bm25_score)]，按分数降序。"""
        if self.is_empty():
            return []
        scores: dict[str, float] = {}
        for t in set(tokenize(query)):
            df = self.df.get(t, 0)
            if df == 0:
                continue
            idf = math.log(1 + (self.corpus_size - df + 0.5) / (df + 0.5))
            for cid, cnt in self.tf.items():
                f = cnt.get(t, 0)
                if f == 0:
                    continue
                dl = self.doc_len.get(cid, 0)
                denom = f + _K1 * (1 - _B + _B * dl / self.avgdl)
                scores[cid] = scores.get(cid, 0.0) + idf * (f * (_K1 + 1)) / denom
        ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
        return ranked

    # ---------- 持久化 ----------
    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _TOKENIZER_VERSION,
            "corpus_size": self.corpus_size,
            "avgdl": self.avgdl,
            "doc_len": self.doc_len,
            "tf": self.tf,
            "df": self.df,
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            p = json.loads(self.path.read_text(encoding="utf-8"))
            if p.get("version") != _TOKENIZER_VERSION:
                self.corpus_size = 0  # 旧分词器索引，触发重建
                return
            self.corpus_size = p.get("corpus_size", 0)
            self.avgdl = p.get("avgdl", 1.0)
            self.doc_len = p.get("doc_len", {})
            self.tf = p.get("tf", {})
            self.df = p.get("df", {})
        except Exception:
            self.corpus_size = 0
