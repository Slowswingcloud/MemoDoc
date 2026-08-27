"""Step 1 验证：跨语言检索（中文查询 ↔ 英文论文）。

重点看 E/F 两个「无标题纯主题」查询——这是翻译检索发挥作用的关键场景。
    .venv\\Scripts\\python.exe scripts\\diag_crosslingual.py
"""
from __future__ import annotations

from memodoc.pipeline import Pipeline

QUERIES = [
    ("A 简称+摘要", "Agent-OS论文的摘要内容是什么", "Agent Operating Systems"),
    ("C 简称+贡献", "Agent-OS论文的主要贡献是什么", "Agent Operating Systems"),
    ("E 纯主题（跨语言关键）", "什么是代理操作系统", "Agent Operating Systems"),
    ("F 纯主题+贡献", "代理操作系统的架构和贡献", "Agent Operating Systems"),
]


def main() -> None:
    p = Pipeline()
    p.retriever._ensure_sparse()
    print("BM25 稀疏索引块数（自动按新版分词重建）:", p.retriever.sparse.corpus_size)
    for label, q, expect in QUERIES:
        rs = p.retriever.retrieve(q, top_k=4, use_rerank=False)
        print(f"\n== {label}: {q}")
        for r in rs:
            mark = " ← 目标文档" if expect in r.doc_name else ""
            head = r.text[:45].replace("\n", " ")
            print(f"  #{r.index} {r.score:.3f} [{r.doc_name[:38]}] {head}{mark}")
        try:
            print("  回答:", p.answer("xl", q).strip()[:180])
        except Exception as e:  # noqa: BLE001
            print("  回答失败:", e)


if __name__ == "__main__":
    main()
