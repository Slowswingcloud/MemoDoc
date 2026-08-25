"""本地 embedding：sentence-transformers + bge-small-zh。

加载失败时自动降级（available=False），检索层会回退到关键词匹配。
"""
from __future__ import annotations

import logging

from memodoc.config import settings

logger = logging.getLogger("memodoc.embedder")

# bge 中文检索查询的官方指令前缀（检索时拼接在查询前，能显著提升召回）
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


class Embedder:
    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or settings.embed_model
        self.device = device or settings.embed_device
        self._model = None
        self.available = False
        self._load_error: str | None = None
        self._tried = False

    def _load(self) -> None:
        if self._model is not None or self._tried:
            return
        self._tried = True
        try:
            from sentence_transformers import SentenceTransformer

            local = settings.model_dir
            if local.exists() and any(local.iterdir()):
                self._model = SentenceTransformer(str(local), device=self.device)
                logger.info("embedding 模型从本地加载：%s", local)
            else:
                self._model = SentenceTransformer(self.model_name, device=self.device)
                logger.info("embedding 模型加载成功：%s", self.model_name)
            self.available = True
        except Exception as e:  # noqa: BLE001
            self._load_error = str(e)
            self.available = False
            logger.warning(
                "embedding 模型加载失败，将回退关键词检索（可运行 `memodoc download-model` 下载模型）：%s", e
            )

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        self._load()
        if not self.available:
            return None
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=settings.embed_batch_size,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]
