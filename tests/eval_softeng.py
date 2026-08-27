"""软件工程课程文档评测用例：检索三档对比 + 引用准确率 + 关键词覆盖 + 引用核查。

覆盖文档（data/uploads/，中文 Markdown，有章节路径）：
- 4需求分析.md / 5软件概要设计.md / 2软件与软件工程.md
- 3软件过程管理.md / 小学期任务分工.md

用法（先给课程文档打"课程"标签；可用 --tags 覆盖）：
    .venv\\Scripts\\python.exe tests\\eval_softeng.py
    .venv\\Scripts\\python.exe tests\\eval_softeng.py --tags 课程

gold_section = 答案所在章节路径的子串；expect = 回答必须包含的关键词。
"""
from __future__ import annotations

import argparse
import re

from memodoc.pipeline import Pipeline

QA = [
    # ---- 4需求分析.md ----
    {"q": "软件需求有哪三个层次？", "gold_section": "软件需求三个层次",
     "expect": ["业务需求", "用户需求", "系统需求"], "tags": ["课程"]},
    {"q": "IEEE 对软件需求的定义包含哪几方面？", "gold_section": "IEEE定义",
     "expect": ["条件", "能力", "文档"], "tags": ["课程"]},
    {"q": "非功能性需求包括哪些内容？", "gold_section": "非功能性需求",
     "expect": ["性能", "约束"], "tags": ["课程"]},
    {"q": "需求获取的方法有哪些？", "gold_section": "需求获取方法",
     "expect": ["访谈", "问卷", "原型"], "tags": ["课程"]},
    {"q": "需求工程的基本流程分几个阶段？", "gold_section": "需求工程基本流程",
     "expect": ["阶段"], "tags": ["课程"]},
    {"q": "软件需求有什么特点？", "gold_section": "软件需求的特点",
     "expect": ["隐式", "易变", "多源"], "tags": ["课程"]},
    # ---- 5软件概要设计.md ----
    {"q": "内聚类型从低到高有哪些？", "gold_section": "内聚类型",
     "expect": ["内聚"], "tags": ["课程"]},
    {"q": "耦合类型从低到高有哪些？", "gold_section": "耦合类型",
     "expect": ["耦合"], "tags": ["课程"]},
    {"q": "GoF 三大类设计模式是什么？", "gold_section": "GoF三大类模式",
     "expect": ["创建型", "结构型", "行为型"], "tags": ["课程"]},
    {"q": "常见的架构风格有哪些？", "gold_section": "常见架构风格",
     "expect": ["分层", "微服务", "MVC"], "tags": ["课程"]},
    {"q": "信息隐藏原则的核心思想是什么？", "gold_section": "信息隐藏原则",
     "expect": ["信息隐藏"], "tags": ["课程"]},
    {"q": "软件设计的基本原则有哪七项？", "gold_section": "七项原则",
     "expect": ["七项"], "tags": ["课程"]},
    # ---- 2软件与软件工程.md ----
    {"q": "软件和程序有什么区别？", "gold_section": "软件 ≠ 程序",
     "expect": ["软件", "程序"], "tags": ["课程"]},
    {"q": "软件开发的基本过程包括哪些？", "gold_section": "软件开发基本过程",
     "expect": ["需求分析", "设计", "编码"], "tags": ["课程"]},
    {"q": "软件由哪些部分组成？", "gold_section": "软件组成",
     "expect": ["程序", "数据"], "tags": ["课程"]},
    # ---- 3软件过程管理.md ----
    {"q": "软件过程的定义是什么？", "gold_section": "软件过程（Software Process）",
     "expect": ["开发", "维护", "项目管理"], "tags": ["课程"]},
    {"q": "软件开发活动包含哪两个核心要素？", "gold_section": "过程（Process）",
     "expect": ["活动", "关系"], "tags": ["课程"]},
    # ---- 小学期任务分工.md ----
    {"q": "UC06 实验练习服务由谁负责？", "gold_section": "业务用例分组",
     "expect": ["吴本昭"], "tags": ["课程"]},
    {"q": "吴本昭在项目中主要负责什么？", "gold_section": "人员与职责",
     "expect": ["实验", "测试"], "tags": ["课程"]},
]

_CITE_RE = re.compile(r"\[(\d+)\]")


def _hit(retrieved, gold: str) -> list[int]:
    return [r.index for r in retrieved if gold in r.section]


def _scope(item: dict, args) -> list[str] | None:
    if args.tags:
        return args.tags
    return item.get("tags")


def main() -> None:
    parser = argparse.ArgumentParser(description="MemoDoc 软件工程课程文档评测")
    parser.add_argument("--tags", nargs="*", default=None, help="按标签限定检索范围（默认用各用例的 tags）")
    args = parser.parse_args()

    pipe = Pipeline()
    print("已索引文档：", pipe.indexed_docs() or "(无)")
    pipe.retriever.reranker._load()
    print("重排模型可用：", "是" if pipe.retriever.reranker.available else "否（将跳过重排）")
    print("检索范围标签：", args.tags or "各用例默认（课程）")

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

        dense_hit = _hit(pipe.retriever._dense(q, 4, tags=scope), gold)
        hybrid_hit = _hit(pipe.retriever.retrieve(q, top_k=4, use_rerank=False, tags=scope), gold)
        rec["dense"] += bool(dense_hit)
        rec["hybrid"] += bool(hybrid_hit)

        final_retrieved = pipe.retriever.retrieve(q, top_k=4, tags=scope)
        final_hit = _hit(final_retrieved, gold)
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
            print("    ⚠ gold_section 未命中，top-4 章节：", [r.section[:40] for r in final_retrieved])
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
