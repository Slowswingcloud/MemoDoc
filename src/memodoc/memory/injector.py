"""记忆注入：新会话/新问题时，检索相关记忆并拼成提示片段（也可用于增强检索查询）。"""
from __future__ import annotations

from memodoc.memory.store import MemoryStore


class MemoryInjector:
    def __init__(self, store: MemoryStore):
        self.store = store

    def facts(self, query: str, user_id: str = "default") -> list[dict]:
        """检索与当前问题相关的记忆事实。"""
        return self.store.search(query, user_id=user_id)

    @staticmethod
    def format(facts: list[dict]) -> str:
        """把记忆事实格式化为提示片段。"""
        if not facts:
            return ""
        lines = []
        for f in facts:
            tag = "身份" if f["meta"].get("type") == "identity" else "偏好"
            lines.append(f"- [{tag}] {f['content']}")
        return "\n".join(lines)

    def inject(self, query: str, user_id: str = "default") -> str:
        return self.format(self.facts(query, user_id))
