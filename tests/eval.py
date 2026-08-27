"""MemoDoc 效果评测：检索召回率（三档对比）+ 引用准确率 + 关键词覆盖 + 引用核查通过率。

支持按标签限定检索范围（先给文档打好标签，再评测对应标签的用例）：
    .venv\\Scripts\\python.exe tests\\eval.py                  # 全库
    .venv\\Scripts\\python.exe tests\\eval.py --tags 演示      # 只测"演示"标签的文档
    .venv\\Scripts\\python.exe tests\\eval.py --tags 论文      # 只测"论文"标签的文档

每条 QA 可带 "tags" 字段（默认范围）；命令行 --tags 会覆盖全局。
注意：标签范围内没有文档时，检索会为空 → 分数全 0，请先用 memodoc tag <文档> <标签> 打标签。
"""
from __future__ import annotations

import argparse
import re

from memodoc.pipeline import Pipeline

# 各用例默认的检索标签范围（可按需修改；--tags 可覆盖）
QA = [
    {"q": "加入极客社需要满足哪些条件？", "gold_section": "入社条件", "expect": ["大一", "面试", "30"], "tags": ["演示"]},
    {"q": "每周例会在什么时间、什么地点？", "gold_section": "每周例会", "expect": ["周三", "B201"], "tags": ["演示"]},
    {"q": "无故缺席一次例会会被扣多少积分？", "gold_section": "请假规则", "expect": ["3"], "tags": ["演示"]},
    {"q": "单次报销的金额上限是多少？", "gold_section": "报销额度", "expect": ["200"], "tags": ["演示"]},
    {"q": "担任一次主题分享主讲能获得多少积分？", "gold_section": "积分获取", "expect": ["10"], "tags": ["演示"]},
    {"q": "技术部主要负责哪些工作？", "gold_section": "技术部", "expect": ["培训", "比赛"], "tags": ["演示"]},
    {"q": "退社时已经缴纳的社费可以退还吗？", "gold_section": "退社", "expect": ["不予退还"], "tags": ["演示"]},
]

_CITE_RE = re.compile(r"\[(\d+)\]")


def _hit(retrieved, gold: str) -> list[int]:
    return [r.index for r in retrieved if gold in r.section]


def _scope(item: dict, args) -> list[str] | None:
    # 命令行 --tags 优先；未指定时用该用例自带的 tags 字段；都没有则全库
    if args.tags:
        return args.tags
    return item.get("tags")


def main() -> None:
    parser = argparse.ArgumentParser(description="MemoDoc 评测")
    parser.add_argument("--tags", nargs="*", default=None, help="按标签限定检索范围（如：演示 论文）")
    args = parser.parse_args()

    pipe = Pipeline()
    print("已索引文档：", pipe.indexed_docs() or "(无)")
    pipe.retriever.reranker._load()
    print("重排模型可用：", "是" if pipe.retriever.reranker.available else "否（将跳过重排）")
    print("检索范围：", args.tags or "全部文档")

    n = len(QA)
    rec = {"dense": 0, "hybrid": 0, "final": 0}
    cite_hits = kw_hits = 0
    check_pass = check_n = 0

    print("\n" + "=" * 80)
    for i, item in enumerate(QA, 1):
        q, gold = item["q"], item["gold_section"]
        scope = _scope(item, args)

        if scope and not pipe.vector_store.all_chunks(tags=scope):
            print(f"  ⚠ 标签 {scope} 内没有文档块——请先执行：memodoc tag <文档名> {' '.join(scope)}")

        # 检索层三档对比（dense/hybrid 不触发重排，速度快）
        dense_hit = _hit(pipe.retriever._dense(q, 4, tags=scope), gold)
        hybrid_hit = _hit(pipe.retriever.retrieve(q, top_k=4, use_rerank=False, tags=scope), gold)
        rec["dense"] += bool(dense_hit)
        rec["hybrid"] += bool(hybrid_hit)

        # 线上管道：混合 + 重排（只重排一次，生成复用该结果）
        final_retrieved = pipe.retriever.retrieve(q, top_k=4, tags=scope)
        final_hit = _hit(final_retrieved, gold)
        rec["final"] += bool(final_hit)

        ans = pipe.answer("eval", q, use_memory=False, retrieved=final_retrieved)
        cited = sorted({int(m) for m in _CITE_RE.findall(ans)})
        cite_ok = any(c in final_hit for c in cited)
        kw_ok = all(e in ans for e in item["expect"]) if item["expect"] else True
        cite_hits += cite_ok
        kw_hits += kw_ok

        checks = pipe.check_citations(ans, final_retrieved)
        for st in checks.values():
            check_n += 1
            check_pass += st == "supported"

        print(f"[{i}/{n}] Q: {q}")
        print(
            f"    recall dense {'✓' if dense_hit else '✗'} | "
            f"hybrid {'✓' if hybrid_hit else '✗'} | "
            f"+rerank {'✓' if final_hit else '✗'}    引用 {'✓' if cite_ok else '✗'}    关键词 {'✓' if kw_ok else '✗'}"
        )
        print(f"    引用编号 {cited}  核查 {checks}")
        print(f"    回答: {ans.strip()[:100]}")

    print("=" * 80)
    print(f"recall@4 纯向量        : {rec['dense']}/{n} = {rec['dense']/n:.0%}")
    print(f"recall@4 混合(BM25+向量): {rec['hybrid']}/{n} = {rec['hybrid']/n:.0%}")
    print(f"recall@4 混合+重排     : {rec['final']}/{n} = {rec['final']/n:.0%}")
    print(f"引用准确率             : {cite_hits}/{n} = {cite_hits/n:.0%}")
    print(f"答案关键词覆盖         : {kw_hits}/{n} = {kw_hits/n:.0%}")
    print(f"引用核查通过率         : {check_pass}/{check_n} = {check_pass/max(check_n, 1):.0%}")


if __name__ == "__main__":
    main()
