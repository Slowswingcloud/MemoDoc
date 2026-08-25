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

    # ---- 检索 ----
    top_k: int = 4
    chunk_size: int = 500
    chunk_overlap: int = 80

    # ---- 记忆 ----
    memory_top_k: int = 5
    memory_sim_threshold: float = 0.85

    # ---- 存储路径 ----
    data_dir: Path = ROOT / "data"
    store_dir: Path = ROOT / "data" / "store"
    session_dir: Path = ROOT / "data" / "sessions"

    @property
    def llm_configured(self) -> bool:
        return bool(self.deepseek_api_key)


settings = Settings()

# 在加载任何模型前，把下载端点确定性地写入环境（.env / 环境变量均可覆盖）
os.environ["HF_ENDPOINT"] = settings.hf_endpoint
