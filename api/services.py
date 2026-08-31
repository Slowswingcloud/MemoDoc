"""产品层服务：文档分类元数据、学习画像抽取、班级薄弱点统计。

设计约束：只组合现有 pipeline / 存储的【公开接口】或直接读数据文件，
不修改 src/ 下任何 RAG / Memory 文件（master 分支用于项目复现，核心逻辑冻结）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from memodoc.config import settings
from memodoc.pipeline import Pipeline

DOC_META_PATH = settings.store_dir / "doc_meta.json"
MEMORIES_PATH = settings.store_dir / "memories.json"

_LEARNING_SYSTEM = (
    "你是学习状态抽取器。从学生与学习助手的问答中，抽取关于该学生的【学习状态】事实。\n"
    "只抽取以下类型：\n"
    "- 薄弱知识点：学生表示不会/不懂/经常错的某个知识点或概念；\n"
    "- 掌握情况：学生明确表示已经掌握/理解了某内容；\n"
    "- 常错题型：学生经常出错的题型或题目类型。\n"
    "规则：\n"
    "1. 只输出 JSON 数组，不要任何解释；\n"
    "2. 每项格式：{\"type\": \"learning\", \"subject\": \"薄弱知识点|掌握情况|常错题型\", \"content\": \"具体陈述\"}；\n"
    "3. 只抽取学生明确表达的内容，不推断；\n"
    "4. 没有可抽取的内容时输出 []。\n"
)


class DocService:
    """文档分类元数据（course/doc_type），独立于 RAG 注册表，避免改动 src/。"""

    def __init__(self, pipe: Pipeline):
        self.pipe = pipe
        self.path = DOC_META_PATH
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")

    def upsert(self, doc_name: str, source: str, course: str, doc_type: str, chunks: int) -> None:
        self._data[doc_name] = {
            "source": source,
            "course": course,
            "doc_type": doc_type,
            "chunks": chunks,
            "indexed_at": time.time(),
        }
        self._save()

    def remove(self, doc_name: str) -> None:
        self._data.pop(doc_name, None)
        self._save()

    def list(self, course: str | None = None, doc_type: str | None = None) -> list[dict]:
        """合并 RAG 注册表（基础信息）与本层分类元数据。"""
        base = {d["name"]: d for d in self.pipe.documents()}
        out = []
        for name, base_info in base.items():
            meta = self._data.get(name, {})
            item = {
                "name": name,
                "source": base_info.get("source", meta.get("source", "")),
                "chunks": base_info.get("chunks", meta.get("chunks", 0)),
                "indexed_at": base_info.get("indexed_at", meta.get("indexed_at", 0)),
                "course": meta.get("course", "未分类"),
                "doc_type": meta.get("doc_type", "其他"),
            }
            if course and item["course"] != course:
                continue
            if doc_type and item["doc_type"] != doc_type:
                continue
            out.append(item)
        out.sort(key=lambda x: x.get("indexed_at", 0), reverse=True)
        return out

    def courses(self) -> list[str]:
        return sorted({d.get("course", "未分类") for d in self.list()})


class LearningService:
    """学习画像：抽取 learning 事实（独立 LLM 调用）→ 学生画像 / 班级统计。"""

    def __init__(self, pipe: Pipeline):
        self.pipe = pipe

    def extract(self, question: str, answer: str, user_id: str) -> None:
        """每轮学生问答后调用：把 learning 事实写入记忆库（走 MemoryStore 公开 add 接口）。"""
        try:
            data = self.pipe.generator.llm.chat_json(
                [
                    {"role": "system", "content": _LEARNING_SYSTEM},
                    {"role": "user", "content": f"学生：{question}\n助手：{answer}\n\n请抽取学习状态事实（JSON 数组）："},
                ]
            )
            if not isinstance(data, list):
                return
            for item in data:
                if not isinstance(item, dict):
                    continue
                content = (item.get("content") or "").strip()
                if content:
                    self.pipe.memory_store.add(
                        {
                            "type": "learning",
                            "subject": (item.get("subject") or "薄弱知识点").strip(),
                            "content": content,
                        },
                        user_id,
                    )
        except Exception:
            pass

    def profile(self, user_id: str) -> list[dict]:
        facts = self.pipe.list_memories(user_id)
        return [
            {"type": f["meta"].get("type"), "subject": f["meta"].get("subject", ""), "content": f["content"]}
            for f in facts
            if f["meta"].get("type") == "learning"
        ]

    def class_stats(self) -> list[dict]:
        """聚合所有学生（非教师）的 learning 事实，按出现次数降序。

        直接读取 memories.json（数据文件），不依赖内存私有接口。
        """
        facts: list[dict] = []
        if MEMORIES_PATH.exists():
            try:
                facts = json.loads(MEMORIES_PATH.read_text(encoding="utf-8"))
            except Exception:
                facts = []
        groups: dict[str, dict] = {}
        for it in facts:
            meta = it.get("meta", {})
            if meta.get("type") != "learning":
                continue
            uid = meta.get("user_id", "")
            if uid in ("tea", "teacher", "default", ""):
                continue
            key = f"{meta.get('subject', '')}|{it.get('text', '')}"
            g = groups.setdefault(
                key,
                {
                    "subject": meta.get("subject", "薄弱知识点"),
                    "content": it.get("text", ""),
                    "count": 0,
                    "students": set(),
                },
            )
            g["count"] += 1
            g["students"].add(uid)
        out = [
            {"subject": g["subject"], "content": g["content"], "count": g["count"], "students": len(g["students"])}
            for g in groups.values()
        ]
        out.sort(key=lambda x: -x["count"])
        return out
