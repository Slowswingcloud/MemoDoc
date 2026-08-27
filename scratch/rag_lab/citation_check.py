"""Step 4 手搓：引用核查（LLM 裁判）。

任务：实现 check_citations，跑通 `python verify.py 4`。
用 DeepSeek（openai SDK，OpenAI 兼容）当裁判：给回答 + 编号片段，输出 JSON 判定。
禁止 import memodoc 内部模块。
"""
from __future__ import annotations

import os
import re

from openai import OpenAI

_CITE_RE = re.compile(r"\[(\d+)\]")
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
    return _client


def check_citations(answer: str, chunks: list[dict]) -> dict[int, str]:
    """逐条核查回答中的 [n] 引用是否被对应片段支持。

    chunks: list[dict]，每个含 "index"（引用编号）和 "text"。
    返回 {n: "supported" | "unsupported" | "unknown"}；无引用返回 {}。

    TODO: 实现（解析 [n] → 拼 prompt → LLM 返回 JSON → 容错解析）
    """
    return {}
