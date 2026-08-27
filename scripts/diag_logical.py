"""Step 2 验证：逻辑空间（租户/生命周期物理文件夹 + 虚拟标签扁平化）。

    .venv\\Scripts\\python.exe scripts\\diag_logical.py
"""
from __future__ import annotations

from pathlib import Path

from memodoc.config import settings
from memodoc.pipeline import Pipeline

DOC = "data/demo_doc.md"
TENANT, LIFE, TAGS = "t1", "archive", ["演示", "测试"]


def main() -> None:
    p = Pipeline()

    print("== ① 索引（带租户/生命周期/虚拟标签）")
    print("  ", p.index(DOC, tenant=TENANT, lifecycle=LIFE, tags=TAGS))

    phys = settings.upload_dir / TENANT / LIFE / "demo_doc.md"
    print(f"\n== ② 物理层按租户/生命周期归档: {phys.exists()} → {phys}")
    print("   uploads 目录结构（应为 t1/archive/… 子目录）：")
    for d in sorted(settings.upload_dir.rglob("*")):
        if d.is_file():
            print("   ", d.relative_to(settings.upload_dir))

    chunks = p.vector_store.all_chunks(doc_name="demo_doc", tenant=TENANT)
    print(f"\n== ③ 逻辑层扁平 + 虚拟标签: 租户过滤 {len(chunks)} 块")
    if chunks:
        m = chunks[0]["meta"]
        print(f"   meta 示例: tenant={m.get('tenant')} lifecycle={m.get('lifecycle')} tags={m.get('tags')}")
    by_tag = p.vector_store.all_chunks(tags=TAGS)
    print(f"   tags={TAGS} 过滤: {len(by_tag)} 块")

    rs_t = p.retriever.retrieve("入社需要满足哪些条件？", top_k=4, use_rerank=False, tenant=TENANT)
    rs_g = p.retriever.retrieve("入社需要满足哪些条件？", top_k=4, use_rerank=False)
    print(f"\n== ④ 检索: 租户 t1 过滤 {len(rs_t)} 条 | 全局 {len(rs_g)} 条（全局应 ≥ 过滤）")

    print("\n== ⑤ 清理并恢复 demo_doc 默认租户")
    p.delete_doc("demo_doc")
    phys.unlink(missing_ok=True)
    print("  ", p.index(DOC))
    print("   恢复完成，demo_doc 回到默认租户。")


if __name__ == "__main__":
    main()
