"""论文问答定位（第 2 轮）：复现并锁定失败场景。

四种查询组合（简称/无标题 × 摘要/贡献），跑完把输出发我：
    .venv\\Scripts\\python.exe scripts\\diag_paper2.py
"""
from __future__ import annotations

from memodoc.pipeline import Pipeline

TARGET = (
    "Agent Operating Systems Agent-OS A Blueprint Architecture "
    "for Real-Time, Secure, and Scalable AI Agents"
)

QUERIES = [
    ("A 简称+摘要", "Agent-OS论文的摘要内容是什么"),
    ("B 无标题+摘要", "这篇论文的摘要内容是什么"),
    ("C 简称+贡献", "Agent-OS论文的主要贡献是什么"),
    ("D 全标题+贡献", f"《{TARGET}》的主要贡献是什么"),
]


def main() -> None:
    p = Pipeline()
    for label, q in QUERIES:
        rs = p.retriever.retrieve(q, top_k=4, use_rerank=False)
        print(f"\n== {label}: {q[:50]}")
        for r in rs:
            head = r.text[:60].replace("\n", " ")
            print(f"  #{r.index} {r.score:.3f}  {head}")
        try:
            print("  回答:", p.answer("d2", q).strip()[:220])
        except Exception as e:  # noqa: BLE001
            print("  回答失败:", e)


if __name__ == "__main__":
    main()
