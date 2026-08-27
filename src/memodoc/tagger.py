"""自动打标签：LLM 建议（优先复用已有标签体系）+ 启发式兜底（零成本）。

LLM 不可用或失败时回退到 fallback_tags（语言 + 文档类型关键词）。
"""
from __future__ import annotations

from memodoc.llm.openai_compat import llm
from memodoc.rag.sparse import _is_english

_PAPER_HINTS = ("abstract", "conference paper", "iclr", "arxiv", "proceedings", "doi:", "corpus")
_COURSE_HINTS = ("课程", "讲义", "教学", "作业", "实验", "考试", "章节", "知识点")
_MANUAL_HINTS = ("手册", "指南", "操作说明", "规范", "使用方法")


def suggest_tags(text: str, existing: list[str] | None = None) -> list[str]:
    """LLM 根据文档内容建议 2-4 个简短标签；失败返回 []。"""
    try:
        existing = existing or []
        prompt = (
            "你是文档标签器。根据下面的文档内容，给出 2-4 个简短标签（每个 2-6 字），"
            "代表文档类型或主题（例如：论文、课程、需求分析、记忆系统、手册）。\n"
            "规则：\n"
            "1. 如果【已有标签】中有合适的，优先复用（保持标签体系一致）；\n"
            "2. 只输出 JSON 数组，例如 [\"论文\", \"记忆系统\"]，不要任何解释。\n\n"
            f"【已有标签】{existing}\n\n"
            f"【文档内容】\n{text[:1500]}\n\n"
            "标签："
        )
        data = llm.chat_json([{"role": "user", "content": prompt}])
        if isinstance(data, list):
            tags = [str(t).strip() for t in data if str(t).strip()]
            return tags[:4]
    except Exception:
        pass
    return []


def fallback_tags(text: str) -> list[str]:
    """零成本兜底：语言 + 文档类型关键词。"""
    tags: list[str] = []
    if _is_english(text):
        tags.append("英文")
        low = text.lower()
        if any(h in low for h in _PAPER_HINTS):
            tags.append("论文")
    else:
        tags.append("中文")
        if any(h in text for h in _COURSE_HINTS):
            tags.append("课程")
        if any(h in text for h in _MANUAL_HINTS):
            tags.append("手册")
    if not tags:
        tags.append("文档")
    return tags
