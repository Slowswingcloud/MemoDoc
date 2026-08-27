"""论文评测用例：跨语言（中文提问 × 英文论文）+ 文档路由 + 检索三档对比。

英文论文分块无章节路径（全标"正文"），所以黄金标准改用**单个有区分度的关键词**：
- gold_kw：答案所在片段必须包含的关键词（取自标题/摘要，保证存在）；命中=召回
- expect：回答必须包含的中文关键词（答案质量）

用法（先确认论文已打"论文"标签；可用 --tags 指定其他标签）：
    .venv\\Scripts\\python.exe tests\\eval_papers.py
    .venv\\Scripts\\python.exe tests\\eval_papers.py --tags 论文

论文清单：Agent-OS / Agentic Memory / MEM1 / MemMachine / Memory-R1 /
          OS Agents Survey / OS-Symphony / Verifiable Memory
"""
from __future__ import annotations

import argparse
import re

from memodoc.pipeline import Pipeline

QA = [
    # ---- Agent-OS（蓝图书）----
    {"q": "Agent-OS论文提出了什么架构模型？", "paper": "Agent Operating Systems Agent-OS",
     "gold_kw": ["five-layer"], "expect": ["五层", "架构"]},
    {"q": "Agent-OS论文如何保证实时性？", "paper": "Agent Operating Systems Agent-OS",
     "gold_kw": ["latency"], "expect": ["实时"]},
    {"q": "Agent-OS论文的动机是什么？", "paper": "Agent Operating Systems Agent-OS",
     "gold_kw": ["ad-hoc"], "expect": ["操作系统", "缺乏"]},
    {"q": "Agent-OS论文如何设计安全机制？", "paper": "Agent Operating Systems Agent-OS",
     "gold_kw": ["microkernel"], "expect": ["安全"]},
    # ---- Agentic Memory ----
    {"q": "Agentic Memory论文如何统一长期与短期记忆管理？", "paper": "Agentic Memory Learning",
     "gold_kw": ["short-term"], "expect": ["长期", "短期"]},
    # ---- MEM1 ----
    {"q": "MEM1论文如何协同记忆与推理？", "paper": "MEM1",
     "gold_kw": ["synergize"], "expect": ["记忆", "推理"]},
    # ---- MemMachine ----
    {"q": "MemMachine论文的记忆系统有什么特点？", "paper": "MemMachine",
     "gold_kw": ["ground-truth"], "expect": ["记忆", "个性化"]},
    # ---- Memory-R1 ----
    {"q": "Memory-R1论文用什么方法增强智能体的记忆管理？", "paper": "Memory-R1",
     "gold_kw": ["reinforcement"], "expect": ["强化学习", "记忆"]},
    # ---- OS Agents Survey ----
    {"q": "OS Agents综述论文调研了哪些方向的智能体？", "paper": "OS Agents A Survey",
     "gold_kw": ["MLLM"], "expect": ["综述", "智能体"]},
    # ---- OS-Symphony ----
    {"q": "OS-Symphony论文提出了什么框架？", "paper": "OS-Symphony",
     "gold_kw": ["generalist"], "expect": ["框架"]},
    # ---- Verifiable Memory ----
    {"q": "Verifiable Memory论文如何验证智能体记忆？", "paper": "Verifiable Memory",
     "gold_kw": ["verifier"], "expect": ["验证", "记忆"]},
]

_CITE_RE = re.compile(r"\[(\d+)\]")


def _chunk_hit(retrieved, gold_kw: list[str]) -> list[int]:
    """命中片段：文本包含全部 gold_kw（忽略大小写）。"""
    hits = []
    for r in retrieved:
        low = r.text.lower()
        if all(k.lower() in low for k in gold_kw):
            hits.append(r.index)
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description="MemoDoc 论文评测（跨语言 + 路由 + 三档对比）")
    parser.add_argument("--tags", nargs="*", default=["论文"], help="标签范围（默认：论文）")
    args = parser.parse_args()

    pipe = Pipeline()
    print("已索引文档：", pipe.indexed_docs() or "(无)")
    pipe.retriever.reranker._load()
    print("重排模型可用：", "是" if pipe.retriever.reranker.available else "否（将跳过重排）")
    print("检索范围标签：", args.tags)

    n = len(QA)
    rec = {"dense": 0, "hybrid": 0, "final": 0}
    cite_hits = kw_hits = 0
    check_pass = check_n = 0

    print("\n" + "=" * 84)
    for i, item in enumerate(QA, 1):
        q = item["q"]
        route = pipe.retriever._route_doc(item["paper"])

        dense_hit = _chunk_hit(
            pipe.retriever._dense(q, 4, doc_name=route, tags=args.tags), item["gold_kw"]
        )
        hybrid_hit = _chunk_hit(
            pipe.retriever.retrieve(q, top_k=4, use_rerank=False, doc_name=route, tags=args.tags),
            item["gold_kw"],
        )
        final_retrieved = pipe.retriever.retrieve(q, top_k=4, doc_name=route, tags=args.tags)
        final_hit = _chunk_hit(final_retrieved, item["gold_kw"])
        rec["dense"] += bool(dense_hit)
        rec["hybrid"] += bool(hybrid_hit)
        rec["final"] += bool(final_hit)

        ans = pipe.answer("evalp", q, retrieved=final_retrieved)
        cited = sorted({int(m) for m in _CITE_RE.findall(ans)})
        cite_ok = any(c in final_hit for c in cited)
        kw_ok = all(e in ans for e in item["expect"])
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
            f"+rerank {'✓' if final_hit else '✗'}    引用 {'✓' if cite_ok else '✗'}    "
            f"关键词 {'✓' if kw_ok else '✗'}"
        )
        print(f"    gold_kw命中 {final_hit}  引用 {cited}  核查 {checks}")
        if not final_hit:
            print(f"    ⚠ top-4 未命中 {item['gold_kw']}，块预览：")
            for r in final_retrieved:
                print(f"      [#{r.index}] {r.text[:64].replace(chr(10), ' ')}")
        print(f"    回答: {ans.strip()[:110]}")

    print("=" * 84)
    print(f"recall@4 纯向量        : {rec['dense']}/{n} = {rec['dense']/n:.0%}")
    print(f"recall@4 混合(BM25+向量): {rec['hybrid']}/{n} = {rec['hybrid']/n:.0%}")
    print(f"recall@4 混合+重排     : {rec['final']}/{n} = {rec['final']/n:.0%}")
    print(f"引用准确率             : {cite_hits}/{n} = {cite_hits/n:.0%}")
    print(f"答案关键词覆盖         : {kw_hits}/{n} = {kw_hits/n:.0%}")
    print(f"引用核查通过率         : {check_pass}/{check_n} = {check_pass/max(check_n, 1):.0%}")


if __name__ == "__main__":
    main()
