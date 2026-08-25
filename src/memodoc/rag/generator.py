"""生成器：拼装系统提示（规则 + 记忆 + 编号片段），流式输出并强制 [n] 引用。"""
from __future__ import annotations

import re

from memodoc.llm.openai_compat import LLMClient
from memodoc.rag.retriever import Retrieved

_CITE_RE = re.compile(r"\[\d+\]")

SYSTEM_PROMPT = """你是 MemoDoc，一个严谨的中文文档问答助手。

严格遵循以下规则：
1. 只能依据下方【文档片段】回答，禁止使用你自己的外部知识。
2. 引用来源时用方括号编号标注，例如 [1] 或 [2][3]；编号必须严格对应下方【文档片段】里实际存在的编号，不得编造编号；如果下方没有任何片段，禁止输出任何 [n] 引用。
3. 如果片段不足以回答，直接回答"文档中没有相关信息"，绝不编造。
4. 用简洁、准确的中文回答；先给结论，再给必要细节。
"""


class Generator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def build_messages(
        self,
        question: str,
        retrieved: list[Retrieved],
        memories: str = "",
        history: list[dict] | None = None,
    ) -> list[dict]:
        parts = [SYSTEM_PROMPT]
        if memories:
            parts.append("【关于当前用户的长期记忆】\n" + memories)
        parts.append("【文档片段】")
        if retrieved:
            for r in retrieved:
                parts.append(f"[{r.index}] (来源：{r.section or r.doc_name})\n{r.text}")
        else:
            parts.append("（本次没有检索到任何相关文档片段）")
        system = "\n\n".join(parts)

        messages: list[dict] = [{"role": "system", "content": system}]
        for h in history or []:
            content = h["content"]
            # 历史里上一轮的 [n] 编号指向的是那一轮的片段，本轮已失效，剥掉以防误引
            if h["role"] == "assistant":
                content = _CITE_RE.sub("", content)
            messages.append({"role": h["role"], "content": content})
        messages.append({"role": "user", "content": question})
        return messages

    def stream(self, messages: list[dict]):
        yield from self.llm.chat_stream(messages)

    def complete(self, messages: list[dict]) -> str:
        return self.llm.chat(messages)
