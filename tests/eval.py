"""MemoDoc 效果评测：检索召回率 + 引用准确率 + 关键词覆盖。

用法（需先索引 data/demo_doc.md 并配置 API key）：
    uv run memodoc index data/demo_doc.md
    uv run python tests/eval.py
"""
from __future__ import annotations

import re

from memodoc.pipeline import Pipeline

# gold_section：答案所在的章节（section_path 的子串）
QA = [
    {"q": "加入极客社需要满足哪些条件？", "gold_section": "入社条件", "expect": ["大一", "面试", "30"]},
    {"q": "每周例会在什么时间、什么地点？", "gold_section": "每周例会", "expect": ["周三", "B201"]},
    {"q": "无故缺席一次例会会被扣多少积分？", "gold_section": "请假规则", "expect": ["3"]},
    {"q": "单次报销的金额上限是多少？", "gold_section": "报销额度", "expect": ["200"]},
    {"q": "担任一次主题分享主讲能获得多少积分？", "gold_section": "积分获取", "expect": ["10"]},
    {"q": "技术部主要负责哪些工作？", "gold_section": "技术部", "expect": ["培训", "比赛"]},
    {"q": "退社时已经缴纳的社费可以退还吗？", "gold_section": "退社", "expect": ["不予退还"]},
]

_CITE_RE = re.compile(r"\[(\d+)\]")


def main() -> None:
    pipe = Pipeline()
    print("已索引文档：", pipe.indexed_docs() or "(无)")

    n = len(QA)
    recall_hits = cite_hits = kw_hits = 0

    print("\n" + "=" * 72)
    for i, item in enumerate(QA, 1):
        q, gold = item["q"], item["gold_section"]
        retrieved = pipe.retriever.retrieve(q, top_k=4)
        gold_idx = [r.index for r in retrieved if gold in r.section]
        recall_ok = bool(gold_idx)

        ans = pipe.answer("eval", q, use_memory=False)
        cited = sorted({int(m) for m in _CITE_RE.findall(ans)})
        cite_ok = any(c in gold_idx for c in cited)
        kw_ok = all(e in ans for e in item["expect"]) if item["expect"] else True

        recall_hits += recall_ok
        cite_hits += cite_ok
        kw_hits += kw_ok

        print(f"[{i}/{n}] Q: {q}")
        print(f"    recall@4: {'✓' if recall_ok else '✗'}  引用准确: {'✓' if cite_ok else '✗'}  "
              f"关键词: {'✓' if kw_ok else '✗'}")
        print(f"    引用编号 {cited}  命中片段 {gold_idx}")
        print(f"    回答: {ans.strip()[:120]}")

    print("=" * 72)
    print(f"检索召回率 recall@4 : {recall_hits}/{n} = {recall_hits/n:.0%}")
    print(f"引用准确率          : {cite_hits}/{n} = {cite_hits/n:.0%}")
    print(f"答案关键词覆盖      : {kw_hits}/{n} = {kw_hits/n:.0%}")


if __name__ == "__main__":
    main()
