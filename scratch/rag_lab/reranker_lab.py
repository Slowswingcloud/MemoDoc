"""Step 3 手搓：交叉编码器重排。

任务：实现 RerankLab，跑通 `python verify.py 3`。
模型已下载到本地：../../data/models/bge-reranker-v2-m3（用 sentence_transformers.CrossEncoder 加载）。
禁止 import memodoc 内部模块。
"""
from __future__ import annotations


class RerankLab:
    def __init__(self, model_path: str = "../../data/models/bge-reranker-v2-m3", device: str = "cpu"):
        """TODO: 懒加载 CrossEncoder（首次调用时才加载，失败时 available=False）。"""
        self.available = False

    def rerank(self, query: str, candidates: list[dict], top_k: int = 4) -> list[dict]:
        """对 (query, 每个候选片段) 逐对打分，按分数降序取 top_k。

        候选片段 dict: {"id","text","section","score"}；返回同结构，score 更新为重排得分。

        TODO: 实现（模型不可用时原样返回 candidates[:top_k]）
        """
        return candidates[:top_k]
