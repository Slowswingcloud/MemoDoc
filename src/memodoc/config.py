"""集中式配置：pydantic-settings 从 .env / 环境变量读取。

所有路径都基于仓库根目录（由本文件位置反推），因此无论从哪个 cwd 启动都稳定。
"""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

# 让 HuggingFace 模型缓存落在项目内（可被环境变量覆盖）。
os.environ.setdefault("HF_HOME", str(ROOT / "data" / ".hf"))

# 本地回环地址直连、不走代理：否则 Gradio 启动自检（httpx 请求 127.0.0.1:7860）
# 会被 HTTP_PROXY 劫持成 502 "Couldn't start the app"。
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- LLM（DeepSeek，OpenAI 兼容；切 Kimi 只需改 base_url/model）----
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2048

    # ---- Embedding ----
    embed_model: str = "BAAI/bge-small-zh-v1.5"
    embed_device: str = "cpu"
    embed_batch_size: int = 32
    # 模型下载源：默认官方 huggingface.co（走系统代理）；可在 .env 改为可用的镜像
    hf_endpoint: str = "https://huggingface.co"
    # 本地模型目录（`memodoc download-model` 下载到这里，加载时优先使用）
    model_dir: Path = ROOT / "data" / "models" / "bge-small-zh-v1.5"

    # ---- Rerank（对齐 Kotaemon：候选重排）----
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_dir: Path = ROOT / "data" / "models" / "bge-reranker-v2-m3"
    use_rerank: bool = True

    # ---- 检索 ----
    top_k: int = 6  # 对齐 Kotaemon：更大上下文，缓解长文档/论文单跳召回不足
    chunk_size: int = 900  # 对齐 Kotaemon（1024）：避免 500 字把摘要/段落劈开
    chunk_overlap: int = 180  # 对齐 Kotaemon（256 量级）：跨块语义不丢失
    # 混合检索：先召回更多候选，融合后交给重排器精排
    retrieve_candidates: int = 30
    # 混合融合权重：final = w * dense_norm + (1-w) * sparse_norm
    hybrid_weight: float = 0.6
    # 跨语言检索：中文查询自动翻译成英文，双语检索后融合（解决"中文问英文文档"）
    enable_query_translation: bool = True
    # LLM 重排（Kotaemon LLMScoring 思路）：cross-encoder 之后对 top-8 再做一次 LLM 打分。
    # 更稳但每问多几次 LLM 调用，默认关闭，按需开启。
    use_llm_rerank: bool = False

    # ---- 记忆 ----
    memory_top_k: int = 5
    memory_sim_threshold: float = 0.85

    # ---- 存储路径 ----
    data_dir: Path = ROOT / "data"
    store_dir: Path = ROOT / "data" / "store"
    session_dir: Path = ROOT / "data" / "sessions"
    upload_dir: Path = ROOT / "data" / "uploads"
    # 逻辑空间：物理层按 租户/生命周期 归档文件；逻辑层保持扁平、用虚拟标签管理
    default_tenant: str = "default"
    default_lifecycle: str = "active"
    # 索引时自动打标签（LLM 建议 + 启发式兜底；关闭后需手动打标签）
    auto_tag_on_index: bool = True

    @property
    def llm_configured(self) -> bool:
        return bool(self.deepseek_api_key)


settings = Settings()

# 在加载任何模型前，把下载端点确定性地写入环境（.env / 环境变量均可覆盖）
os.environ["HF_ENDPOINT"] = settings.hf_endpoint
