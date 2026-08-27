"""Step 1 手搓：BM25 稀疏检索（jieba 分词 + 倒排索引）。

任务：实现 tokenize / build / search，跑通 `python verify.py 1`。
参考：BM25 公式见 README.md；Kotaemon 参考 storages/docstores/elasticsearch.py。
禁止 import memodoc 内部模块。
"""
from __future__ import annotations


def tokenize(text: str) -> list[str]:
    """中文分词：用 jieba.lcut，过滤空白/标点；英文/数字词统一小写（>=2 字符）。

    TODO: 实现
    """
    return []


class BM25Index:
    def __init__(self):
        # TODO: 初始化：corpus_size / avgdl / doc_len / tf / df
        self.corpus_size = 0
        self.avgdl = 1.0

    def build(self, chunks: list[dict]) -> None:
        """chunks: [{"id": ..., "text": ...}]。统计每个片段的词频、文档频率、平均长度。

        TODO: 实现
        """

    def search(self, query: str, top_k: int = 4) -> list[tuple[str, float]]:
        """按 BM25 打分，返回 [(chunk_id, score)]，降序，取前 top_k。

        TODO: 实现（k1=1.5, b=0.75）
        """
        return []
