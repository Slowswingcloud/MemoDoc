"""软件工程课程文档评测（关键词黄金标准，适配 900 字大块：section_path 不再唯一）。

覆盖文档（data/uploads/）：4需求分析 / 5软件概要设计 / 2软件与软件工程 /
                        3软件过程管理 / 小学期任务分工

用法（先确保所有课程文档都有同一标签，如"课程笔记"）：
    .venv\\Scripts\\python.exe tests\\eval_softeng.py --tags 课程笔记

gold_kw = 答案所在片段必须包含的关键词（取自正文内容，非标题——标题已被分块剥离）；
expect  = 回答必须包含的中文关键词。
"""
from __future__ import annotations

import argparse
import re

from memodoc.pipeline import Pipeline

QA = [
    # ---- 4需求分析.md ----
    {"q": "软件需求有哪三个层次？", "gold_kw": ["业务需求"],
     "expect": ["业务需求", "用户需求", "系统需求"]},
    {"q": "IEEE 对软件需求的定义包含哪几方面？", "gold_kw": ["文档化"],
     "expect": ["条件", "能力", "文档"]},
    {"q": "非功能性需求包括哪些内容？", "gold_kw": ["非功能性"],
     "expect": ["响应时间", "身份认证"]},
    {"q": "需求获取的方法有哪些？", "gold_kw": ["访谈"],
     "expect": ["访谈", "问卷", "原型"]},
    {"q": "需求工程的基本流程分几个阶段？", "gold_kw": ["验证需求"],
     "expect": ["阶段"]},
    {"q": "软件需求有什么特点？", "gold_kw": ["隐式"],
     "expect": ["隐式", "易变", "多源"]},
    # ---- 5软件概要设计.md ----
    {"q": "内聚类型从低到高有哪些？", "gold_kw": ["功能内聚"],
     "expect": ["内聚"]},
    {"q": "耦合类型从低到高有哪些？", "gold_kw": ["内容耦合"],
     "expect": ["耦合"]},
    {"q": "GoF 三大类设计模式是什么？", "gold_kw": ["行为型"],
     "expect": ["创建型", "结构型", "行为型"]},
    {"q": "常见的架构风格有哪些？", "gold_kw": ["微服务"],
     "expect": ["分层", "微服务", "MVC"]},
    {"q": "信息隐藏原则的核心思想是什么？", "gold_kw": ["信息隐藏"],
     "expect": ["信息隐藏"]},
    {"q": "软件设计的基本原则有哪七项？", "gold_kw": ["逐步求精"],
     "expect": ["七项"]},
    # ---- 2软件与软件工程.md ----
    {"q": "软件和程序有什么区别？", "gold_kw": ["数据"],
     "expect": ["软件", "程序"]},
    {"q": "软件开发的基本过程包括哪些？", "gold_kw": ["编码实现"],
     "expect": ["需求分析", "设计", "编码"]},
    {"q": "软件由哪些部分组成？", "gold_kw": ["文档"],
     "expect": ["程序", "数据"]},
    # ---- 3软件过程管理.md ----
    {"q": "软件过程的定义是什么？", "gold_kw": ["项目管理"],
     "expect": ["开发", "维护", "项目管理"]},
    {"q": "软件开发活动包含哪两个核心要素？", "gold_kw": ["核心要素"],
     "expect": ["活动", "关系"]},
    # ---- 小学期任务分工.md ----
    {"q": "UC06 实验练习服务由谁负责？", "gold_kw": ["实验练习"],
     "expect": ["吴本昭"]},
    {"q": "吴本昭在项目中主要负责什么？", "gold_kw": ["吴本昭"],
     "expect": ["实验", "测试"]},
]

_CITE_RE = re.compile(r"\[(\d+)\]")


def _chunk_hit(retrieved, gold_kw: list[str]) -> list[int]:
    hits = []
    for r in retrieved:
        low = r.text.lower()
        if all(k.lower() in low for k in gold_kw):
            hits.append(r.index)
    return hits


def _scope(item: dict, args) -> list[str] | None:
    if args.tags:
        return args.tags
    return item.get("tags")


def main() -> None:
    parser = argparse.ArgumentParser(description="MemoDoc 软件工程课程文档评测（关键词标准）")
    parser.add_argument("--tags", nargs="*", default=None, help="按标签限定检索范围（建议传实际标签，如 课程笔记）")
    parser.add_argument("--top-k", type=int, default=6, help="recall 的 k")
    args = parser.parse_args()

    pipe = Pipeline()
    print("已索引文档：", pipe.indexed_docs() or "(无)")
    pipe.retriever.reranker._load()
    print("重排模型可用：", "是" if pipe.retriever.reranker.available else "否（将跳过重排）")
    print("检索范围标签：", args.tags or "全库")

    n = len(QA)
    rec = {"dense": 0, "hybrid": 0, "final": 0}
    cite_hits = kw_hits = 0
    check_pass = check_n = 0

    print("\n" + "=" * 80)
    for i, item in enumerate(QA, 1):
        q = item["q"]
        scope = _scope(item, args)
        if scope and not pipe.vector_store.all_chunks(tags=scope):
            print(f"  ⚠ 标签 {scope} 内没有文档块——请先执行：memodoc tag <文档名> {' '.join(scope)}")

        dense_hit = _chunk_hit(pipe.retriever._dense(q, args.top_k, tags=scope), item["gold_kw"])
        hybrid_hit = _chunk_hit(
            pipe.retriever.retrieve(q, top_k=args.top_k, use_rerank=False, tags=scope),
            item["gold_kw"],
        )
        final_retrieved = pipe.retriever.retrieve(q, top_k=args.top_k, tags=scope)
        final_hit = _chunk_hit(final_retrieved, item["gold_kw"])
        rec["dense"] += bool(dense_hit)
        rec["hybrid"] += bool(hybrid_hit)
        rec["final"] += bool(final_hit)

        ans = pipe.answer("evalse", q, use_memory=False, retrieved=final_retrieved)
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
        if not final_hit:
            print("    ⚠ gold_kw 未命中，top-4 章节：", [r.section[:36] for r in final_retrieved])
        print(f"    引用编号 {cited}  核查 {checks}")
        print(f"    回答: {ans.strip()[:100]}")

    print("=" * 80)
    k = args.top_k
    print(f"recall@{k} 纯向量        : {rec['dense']}/{n} = {rec['dense']/n:.0%}")
    print(f"recall@{k} 混合(BM25+向量): {rec['hybrid']}/{n} = {rec['hybrid']/n:.0%}")
    print(f"recall@{k} 混合+重排     : {rec['final']}/{n} = {rec['final']/n:.0%}")
    print(f"引用准确率             : {cite_hits}/{n} = {cite_hits/n:.0%}")
    print(f"答案关键词覆盖         : {kw_hits}/{n} = {kw_hits/n:.0%}")
    print(f"引用核查通过率         : {check_pass}/{check_n} = {check_pass/max(check_n, 1):.0%}")


if __name__ == "__main__":
    main()
