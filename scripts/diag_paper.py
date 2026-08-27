"""论文问答诊断：定位"问不到摘要/贡献"是 解析 / 检索 / 生成 哪一层的锅。

用法：.venv\\Scripts\\python.exe scripts\\diag_paper.py [论文关键词]
      （不带参数则取已索引的第一篇文档）
"""
from __future__ import annotations

import sys

from memodoc.pipeline import Pipeline


def main() -> None:
    p = Pipeline()
    docs = p.indexed_docs()
    print("== 已索引文档 ==")
    for d in docs:
        print("  -", d)
    if not docs:
        print("（空）")
        return

    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    target = next((d for d in docs if kw and kw.lower() in d.lower()), None) or docs[0]
    print("\n== 诊断对象 ==", target)

    chunks = p.vector_store.all_chunks(doc_name=target)
    print(f"该文档共 {len(chunks)} 块")

    # ---- 层1：解析检查 ----
    abs_hits = [c for c in chunks if "abstract" in c["text"].lower()[:600]]
    print(f"\n[层1 解析] 前600字符含 'Abstract' 的块数: {len(abs_hits)}")
    if abs_hits:
        print("  示例片段前200字符:", abs_hits[0]["text"][:200].replace("\n", " "))
    else:
        print("  ⚠ 没有任何块含 'Abstract' —— 疑似解析失败（乱码 / 扫描件 / 双栏错位）")

    # ---- 层2 检索：中英查询对比 ----
    q_zh = f"《{target}》的摘要内容是什么"
    q_en = f"what is the abstract of the paper {target}"
    for label, q in (("中文查询", q_zh), ("英文查询", q_en)):
        rs = p.retriever.retrieve(q, top_k=4, use_rerank=False)
        print(f"\n[层2 检索] {label}: {q[:40]}")
        for r in rs:
            print(f"  #{r.index} {r.score:.3f}  {r.section[:60]}")
        rank = next((i for i, r in enumerate(rs) if "abstract" in r.text.lower()[:400]), None)
        print(f"  → 摘要块位置: {'#' + str(rank + 1) if rank is not None else '未命中(未进 top-4)'}")

    # ---- 层3 生成 ----
    print("\n[层3 生成] 中文查询的完整回答：")
    try:
        print(" ", p.answer("diag", q_zh))
    except Exception as e:  # noqa: BLE001
        print("  生成失败:", e)


if __name__ == "__main__":
    main()
