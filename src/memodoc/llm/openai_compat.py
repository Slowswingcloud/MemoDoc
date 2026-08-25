"""DeepSeek/Kimi 统一的 OpenAI 兼容客户端。

同时提供：非流式 chat、流式 chat_stream、结构化 JSON chat_json（容错解析）。
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator

from openai import OpenAI

from memodoc.config import settings


class LLMClient:
    """OpenAI 兼容客户端。默认 DeepSeek；换 Kimi 只需改 base_url/model。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or settings.deepseek_api_key
        self.base_url = base_url or settings.deepseek_base_url
        self.model = model or settings.deepseek_model
        self._client: OpenAI | None = None
        if self.api_key:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    @property
    def configured(self) -> bool:
        return self._client is not None

    def _ensure(self) -> None:
        if self._client is None:
            raise RuntimeError(
                "未配置 API key：请在项目根目录的 .env 中设置 DEEPSEEK_API_KEY"
            )

    def chat(self, messages: list[dict], temperature: float | None = None) -> str:
        self._ensure()
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=settings.llm_temperature if temperature is None else temperature,
            max_tokens=settings.llm_max_tokens,
            stream=False,
        )
        return resp.choices[0].message.content or ""

    def chat_stream(self, messages: list[dict], temperature: float | None = None) -> Iterator[str]:
        self._ensure()
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=settings.llm_temperature if temperature is None else temperature,
            max_tokens=settings.llm_max_tokens,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

    def chat_json(self, messages: list[dict]) -> Any:
        """请求 JSON 输出；优先 json_object，失败则回退到容错解析。"""
        self._ensure()
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            return _parse_json(resp.choices[0].message.content or "")
        except Exception:
            return _parse_json(self.chat(messages, temperature=0.0))


def _parse_json(text: str) -> Any:
    """容错解析：去掉代码围栏，必要时提取首个 JSON 对象/数组。"""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        for pat in (r"\[.*\]", r"\{.*\}"):
            m = re.search(pat, text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    continue
    return None


# 模块级单例，供全局复用
llm = LLMClient()
