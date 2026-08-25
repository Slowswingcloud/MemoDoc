"""事实抽取：LLM 从每轮对话中抽取关于用户的长期事实（身份/偏好）。"""
from __future__ import annotations

from memodoc.llm.openai_compat import LLMClient

_EXTRACT_SYSTEM = """你是一个长期记忆抽取器。从用户与助手的对话中，抽取关于"用户"的长期事实。

只抽取以下两类，其余一律忽略：
- identity：用户身份（年级、专业、职业、所在组织、角色等稳定属性）
- preference：用户偏好（表达习惯、关注重点、使用场景、明确提出的喜好）

规则：
1. 只输出一个 JSON 数组，不要任何解释或多余文字。
2. 每项格式：{"type": "identity" 或 "preference", "subject": "简短属性名", "content": "事实陈述"}
3. 只抽取用户明确表达过的内容，不推断、不抽取常识。
4. 没有可抽取的内容时输出 []。
"""


class FactExtractor:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def extract(self, user_msg: str, assistant_msg: str) -> list[dict]:
        prompt = f"用户：{user_msg}\n助手：{assistant_msg}\n\n请抽取关于用户的事实（JSON 数组）："
        messages = [
            {"role": "system", "content": _EXTRACT_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        data = self.llm.chat_json(messages)
        if not isinstance(data, list):
            return []
        facts: list[dict] = []
        seen: set[tuple] = set()
        for item in data:
            if not isinstance(item, dict):
                continue
            t = item.get("type")
            content = (item.get("content") or "").strip()
            if t in ("identity", "preference") and content:
                subject = (item.get("subject") or "其他").strip()
                key = (t, subject, content)
                if key in seen:
                    continue
                seen.add(key)
                facts.append({"type": t, "subject": subject, "content": content})
        return facts
