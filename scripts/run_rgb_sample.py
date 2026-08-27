"""RGB 小样本评测：检索召回率 recall@k + 答案准确率 accuracy。

对每个能力的小样本计算指标：
- recall@k：答案所在文档/片段是否进入检索 top-k
  （优先用问题自带的关联文档信息；否则用参考答案的关键词匹配检索片段）
- accuracy：LLM 裁判（DeepSeek）判定回答与参考答案是否一致
- 拒答能力额外给"拒答准确率"（期望系统答"没有相关信息"）

用法：
    .venv\\Scripts\\python.exe scripts\\run_rgb_sample.py                       # 默认：全部能力 × 2 问
    .venv\\Scripts\\python.exe scripts\\run_rgb_sample.py --ability integration --limit 3
    .venv\\Scripts\\python.exe scripts\\run_rgb_sample.py --ability negative --limit 5

数据来源：优先本地 RGB/ 仓库，否则从 GitHub 下载 zip。
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

import requests

from memodoc.pipeline import Pipeline

RGB_CANDIDATES = [
    "https://codeload.github.com/chen700564/RGB/zip/refs/heads/main",
    "https://codeload.github.com/chen700564/RGB/zip/refs/heads/master",
    "https://codeload.github.com/chen7002/RGB/zip/refs/heads/main",
    "https://codeload.github.com/chen7002/RGB/zip/refs/heads/master",
]
RGB_DIR = Path("RGB")

ABILITY_DIR_HINTS = {
    "negative": ["negative", "reject"],
    "noise": ["noise"],
    "integration": ["integration", "information"],
    "counterfactual": ["counterfactual"],
}

_REFUSE_KW = ("没有", "无相关信息", "不存在", "无法", "未提及", "未找到", "没有找到",
              "no information", "not found", "does not contain")

_RELEVANT_FIELDS = ("relevant_docs", "relevant_doc", "doc_ids", "doc_id", "docs",
                    "documents", "ref_docs", "source_docs", "source")


def _ensure_rgb_data() -> Path:
    if RGB_DIR.exists():
        print(f"使用本地 RGB 仓库：{RGB_DIR}")
        return RGB_DIR
    last_err: str | None = None
    for url in RGB_CANDIDATES:
        try:
            print(f"尝试下载：{url}")
            r = requests.get(url, timeout=300)
            if r.status_code != 200:
                last_err = f"{url} → HTTP {r.status_code}"
                continue
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                z.extractall(".")
            extracted = next(Path(".").glob("RGB-*"), None)
            if extracted and extracted.is_dir():
                shutil.move(str(extracted), str(RGB_DIR))
            print(f"解压完成 → {RGB_DIR}")
            return RGB_DIR
        except Exception as e:  # noqa: BLE001
            last_err = f"{url} → {e}"
    raise RuntimeError(
        f"RGB 数据下载失败：{last_err}\n"
        "请手动执行：git clone https://github.com/chen700564/RGB.git"
    )


def _discover(root: Path, ability: str | None) -> dict:
    data_dir = next(
        (p for p in root.iterdir() if p.is_dir() and p.name.lower() in ("data", "benchmark", "dataset")),
        root,
    )
    found: dict[str, dict] = {}
    for sub in sorted(data_dir.iterdir()):
        if not sub.is_dir():
            continue
        name = sub.name.lower()
        for key, hints in ABILITY_DIR_HINTS.items():
            if ability and key != ability:
                continue
            if any(h in name for h in hints):
                docs = [p for p in sub.rglob("*") if p.is_file() and p.suffix.lower() in (".txt", ".md")]
                qfiles = [p for p in sub.rglob("*") if p.is_file() and p.suffix.lower() == ".json"]
                found[key] = {"dir": sub, "docs": docs, "qfiles": qfiles}
    return found


def _load_questions(qfiles: list[Path], limit: int) -> list[dict]:
    qs: list[dict] = []
    for f in qfiles:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        items = data if isinstance(data, list) else data.get("questions") or data.get("data") or []
        for it in items:
            if isinstance(it, dict) and ("q" in it or "question" in it or "query" in it):
                qs.append({
                    "q": it.get("q") or it.get("question") or it.get("query", ""),
                    "answer": it.get("a") or it.get("answer") or it.get("reference") or it.get("gold", ""),
                    "raw": it,
                })
    return qs[:limit]


def _relevant_docs(item: dict, docs: list[Path]) -> list[Path]:
    """尝试从问题条目中找关联文档（文件名/路径/ID）。"""
    raw = item.get("raw") or {}
    for field in _RELEVANT_FIELDS:
        val = raw.get(field)
        if not val:
            continue
        vals = val if isinstance(val, list) else [val]
        matched = []
        for v in vals:
            v = str(v)
            for d in docs:
                if v.lower() in str(d).lower() or v.lower() in d.stem.lower():
                    matched.append(d)
        if matched:
            return matched
    return []


def _gold_keywords(gold: str) -> list[str]:
    if not gold:
        return []
    kws = [t for t in re.split(r"[\s,，。；;：:、()（）\"'“”]+", gold) if len(t) >= 4]
    kws.sort(key=len, reverse=True)
    return kws[:3]


def _refused(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in _REFUSE_KW)


def _judge(pipe: Pipeline, q: str, answer: str, gold: str) -> bool | None:
    if not gold:
        return None
    try:
        prompt = (
            "判断下面的回答是否与参考答案表达一致（允许措辞不同，但要点必须相同）。"
            "只输出 supported 或 unsupported。\n\n"
            f"回答：{answer}\n\n参考答案：{gold}"
        )
        out = pipe.generator.llm.chat([{"role": "user", "content": prompt}], temperature=0.0)
        return "supported" in out.lower()
    except Exception:
        return None


def _recall(pipe: Pipeline, q: str, rel_docs: list[Path], gold: str, tags: list[str], k: int):
    """返回 (是否命中, top-k 检索结果)。优先关联文档；否则 gold 关键词。"""
    rs = pipe.retriever.retrieve(q, top_k=k, tags=tags)
    if rel_docs:
        names = {d.stem for d in rel_docs}
        return any(r.doc_name in names for r in rs), rs
    kws = _gold_keywords(gold)
    if kws:
        return any(all(k.lower() in r.text.lower() for k in kws) for r in rs), rs
    return None, rs


def main() -> None:
    parser = argparse.ArgumentParser(description="RGB 小样本评测（召回率 + 准确率）")
    parser.add_argument("--ability", choices=["negative", "noise", "integration", "counterfactual", "all"],
                        default="all")
    parser.add_argument("--limit", type=int, default=2, help="每个能力抽几个问题")
    parser.add_argument("--max-docs", type=int, default=10, help="每个能力最多索引几份文档")
    parser.add_argument("--top-k", type=int, default=4, help="recall 的 k")
    args = parser.parse_args()

    root = _ensure_rgb_data()
    abilities = list(ABILITY_DIR_HINTS) if args.ability == "all" else [args.ability]
    found = _discover(root, args.ability)

    if not found:
        print("⚠ 未按预期找到 RGB 能力目录，目录树如下（请发我适配）：")
        for p in sorted(root.rglob("*"))[:60]:
            print("  ", p.relative_to(root))
        sys.exit(1)

    pipe = Pipeline()
    print("=" * 84)
    print(f"{'能力':<14}{'n':>3}{'recall@k':>12}{'accuracy':>12}{'拒答准确率':>12}")
    print("-" * 84)

    for key in abilities:
        info = found.get(key)
        if not info:
            continue
        tag = f"rgb-{key}"
        n_idx = 0
        for doc in info["docs"][: args.max_docs]:
            try:
                pipe.index(str(doc), tags=[tag])
                n_idx += 1
            except Exception:
                pass
        questions = _load_questions(info["qfiles"], args.limit)
        print(f"\n== 能力 {key}：索引 {n_idx} 份文档，样本 {len(questions)} 问 ==")
        if not questions:
            print("  未解析到问题（格式见下，可发我适配）")
            continue

        recall_n = acc_n = refuse_n = 0
        recall_hits = acc_hits = refuse_hits = 0
        for j, item in enumerate(questions, 1):
            rel = _relevant_docs(item, info["docs"])
            hit, rs = _recall(pipe, item["q"], rel, item["answer"], [tag], args.top_k)
            ans = pipe.answer("rgb", item["q"], tags=[tag]).strip()

            if hit is not None:
                recall_n += 1
                recall_hits += int(hit)
            acc = _judge(pipe, item["q"], ans, item["answer"])
            if acc is not None:
                acc_n += 1
                acc_hits += int(acc)
            if key == "negative":
                refuse_n += 1
                refuse_hits += int(_refused(ans))

            rel_mark = f"关联文档 {len(rel)} 份" if rel else "gold关键词"
            print(f"  [{j}] Q: {item['q'][:50]}")
            print(f"      recall {'✓' if hit else ('—' if hit is None else '✗')}({rel_mark})  "
                  f"acc {'✓' if acc else ('—' if acc is None else '✗')}  "
                  f"拒答 {'✓' if _refused(ans) else '—'}")
            print(f"      A: {ans[:130]}")

        r = f"{recall_hits}/{recall_n}" if recall_n else "—"
        a = f"{acc_hits}/{acc_n}" if acc_n else "—"
        f_ = f"{refuse_hits}/{refuse_n}" if refuse_n else "—"
        print(f"{key:<14}{len(questions):>3}{r:>12}{a:>12}{f_:>12}")

        for doc in info["docs"][: args.max_docs]:
            try:
                pipe.delete_doc(doc.stem)
            except Exception:
                pass

    print("\n" + "=" * 84)
    print("说明：recall@k=答案所在文档/片段进 top-k 的比例；accuracy=LLM 裁判判定与参考答案一致的比例；")
    print("拒答准确率仅对 negative 能力有效（期望系统答'没有相关信息'）。")


if __name__ == "__main__":
    main()
