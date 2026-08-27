"""重排：交叉编码器 CrossEncoder（bge-reranker-v2-m3），对齐 Kotaemon 的 rerank retrieval。

流程：混合检索出候选（retrieve_candidates 条）→ 重排器对 (query, 片段) 逐对打分 → 精排 top_k。
模型不可用时自动跳过重排，不影响主链路。
"""
from __future__ import annotations

import logging

from memodoc.config import settings

logger = logging.getLogger("memodoc.reranker")


class Reranker:
    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or settings.reranker_model
        self.device = device or settings.embed_device
        self._model = None
        self.available = False
        self._tried = False

    def _load(self) -> None:
        if self._model is not None or self._tried:
            return
        self._tried = True
        try:
            from sentence_transformers import CrossEncoder

            local = settings.reranker_dir
            if local.exists() and any(local.iterdir()):
                self._model = CrossEncoder(str(local), device=self.device, max_length=512)
                logger.info("重排模型从本地加载：%s", local)
            else:
                self._model = CrossEncoder(self.model_name, device=self.device, max_length=512)
                logger.info("重排模型加载成功：%s", self.model_name)
            self.available = True
        except Exception as e:  # noqa: BLE001
            self.available = False
            logger.warning(
                "重排模型加载失败，跳过重排（可运行 `memodoc download-model --rerank` 下载）：%s", e
            )

    def rerank(self, query: str, candidates: list, top_k: int) -> list:
        """对候选片段精排，返回重排后的 top_k（分数更新为重排得分）。"""
        self._load()
        if not self.available or not candidates:
            return candidates[:top_k]
        pairs = [(query, c.text) for c in candidates]
        scores = self._model.predict(pairs, show_progress_bar=False)
        order = sorted(range(len(candidates)), key=lambda i: -float(scores[i]))
        out = []
        for i in order[:top_k]:
            c = candidates[i]
            c.score = float(scores[i])
            out.append(c)
        return out
