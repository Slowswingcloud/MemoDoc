"""端到端冒烟测试：检索 → 流式生成 → 记忆抽取/注入。

用法：.venv\\Scripts\\python.exe tests/smoke.py
"""
from __future__ import annotations

from memodoc.pipeline import Pipeline


def main() -> None:
    p = Pipeline()
    print("已索引文档：", p.indexed_docs() or "(无)")

    def ask(sid: str, q: str, mem: bool = True) -> str:
        print(f"\n[Q] {q}")
        full = ""
        for delta, retrieved in p.answer_stream(sid, q, use_memory=mem):
            full += delta
        print(f"[A] {full.strip()}")
        print(f"    引用片段编号: {[r.index for r in retrieved]}")
        return full

    ask("demo", "加入极客社需要满足哪些条件？")
    ask("demo", "我是大一新生，刚加入极客社。")

    print("\n== 长期记忆 ==")
    for f in p.list_memories():
        print(f"  - [{f['meta'].get('type')}] {f['meta'].get('subject')}: {f['content']}")

    ask("demo", "我还需要交会费吗？")


if __name__ == "__main__":
    main()
