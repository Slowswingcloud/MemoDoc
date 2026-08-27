#!/usr/bin/env python
"""RAG Lab 自动判分：python verify.py [1|2|3|4|all]

判分器只负责：准备数据、调用你的手搓模块、检查验证点。
不会碰你的实现逻辑；你每完成一步就跑一遍，全绿再进下一步。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))

# 载入 .env（让 citation_check 能读到 DEEPSEEK_API_KEY）
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# 你的手搓模块
import bm25_index as lab_bm25  # noqa: E402
import fusion as lab_fusion  # noqa: E402
import reranker_lab as lab_rerank  # noqa: E402
import citation_check as lab_cite  # noqa: E402

from memodoc.rag.chunker import chunk_text  # noqa: E402
from memodoc.rag.parser import parse_file  # noqa: E402

QA = [
    {"q": "加入极客社需要满足哪些条件？", "gold": "入社条件"},
    {"q": "每周例会在什么时间、什么地点？", "gold": "每周例会"},
    {"q": "无故缺席一次例会会被扣多少积分？", "gold": "请假规则"},
    {"q": "单次报销的金额上限是多少？", "gold": "报销额度"},
    {"q": "担任一次主题分享主讲能获得多少积分？", "gold": "积分获取"},
    {"q": "技术部主要负责哪些工作？", "gold": "技术部"},
    {"q": "退社时已经缴纳的社费可以退还吗？", "gold": "退社"},
]
SPECIAL_Q = {"q": "每周例会在哪里开？", "gold": "每周例会"}


def demo_chunks() -> list[dict]:
    doc = parse_file(str(ROOT / "data" / "demo_doc.md"))
    return [
        {"id": c.id, "text": c.text, "section": c.section_path, "score": 0.0}
        for c in chunk_text(doc.text, doc.name)
    ]


def _ok(cond: bool, name: str, detail: str = "") -> int:
    print(f"  {'✓' if cond else '✗'} {name}" + (f"  ({detail})" if detail and not cond else ""))
    return 0 if cond else 1


def step1(chunks: list[dict]) -> int:
    print("\n[Step 1] BM25 稀疏检索")
    fails = 0
    toks = lab_bm25.tokenize("加入极客社需要满足哪些条件")
    fails += _ok(bool(toks), "tokenize 返回非空", f"得到 {toks!r}")

    idx = lab_bm25.BM25Index()
    idx.build(chunks)
    r1 = idx.search("社费", 4)
    hit = any("社费" in chunks[int(cid.rsplit("#", 1)[-1])]["text"] for cid, _ in r1 if "#" in cid)
    fails += _ok(bool(r1) and hit, "搜「社费」能命中含社费的块", f"返回 {r1[:2]}")

    r2 = idx.search("黑客松", 4)
    hit2 = any("黑客松" in chunks[int(cid.rsplit("#", 1)[-1])]["text"] for cid, _ in r2 if "#" in cid)
    fails += _ok(bool(r2) and hit2, "搜「黑客松」能命中含黑客松的块")

    if r1 and r2:
        rare, common = r2[0][1], idx.search("社团", 1)[0][1]
        fails += _ok(rare > common, "稀有词(黑客松)得分 > 高频词(社团)", f"{rare:.3f} vs {common:.3f}")
    else:
        fails += 1
    return fails


def step2(chunks: list[dict], pipe) -> int:
    print("\n[Step 2] 向量 + BM25 混合融合")
    fails = 0
    idx = lab_bm25.BM25Index()
    idx.build(chunks)
    by_id = {c["id"]: c for c in chunks}

    recall_ok = True
    for item in QA + [SPECIAL_Q]:
        dense = [
            {"id": r.id, "text": r.text, "section": r.section, "score": r.score}
            for r in pipe.retriever._dense(item["q"], 20)
        ]
        sparse = [
            {**by_id[cid], "score": sc} for cid, sc in idx.search(item["q"], 20) if cid in by_id
        ]
        fused = lab_fusion.fuse(dense, sparse, 0.6)
        if not any(item["gold"] in f["section"] for f in fused[:4]):
            recall_ok = False
            print(f"    漏召回: {item['q']} (gold={item['gold']})")
    fails += _ok(recall_ok, f"8 个问题融合后 recall@4 = 100%")

    dense = [{"id": r.id, "text": r.text, "section": r.section, "score": r.score}
             for r in pipe.retriever._dense("每周例会在哪里开？", 20)]
    sparse = [{**by_id[cid], "score": sc} for cid, sc in idx.search("每周例会在哪里开？", 20) if cid in by_id]
    fused = lab_fusion.fuse(dense, sparse, 0.6)
    if not fused:
        fails += _ok(False, "融合分数都在 [0,1]", "fuse 返回空")
        fails += _ok(False, "按分数降序", "fuse 返回空")
    else:
        scores = [f["score"] for f in fused]
        fails += _ok(all(0.0 <= s <= 1.0 + 1e-6 for s in scores), "融合分数都在 [0,1]",
                     f"范围 [{min(scores):.3f},{max(scores):.3f}]")
        fails += _ok(scores == sorted(scores, reverse=True), "按分数降序")
    return fails


def step3(pipe) -> int:
    print("\n[Step 3] 交叉编码器重排")
    fails = 0
    rr = lab_rerank.RerankLab()
    all_ok = True
    for item in [SPECIAL_Q] + QA:
        cands = [
            {"id": r.id, "text": r.text, "section": r.section, "score": r.score}
            for r in pipe.retriever.retrieve(item["q"], top_k=20, use_rerank=False)
        ]
        if not cands:
            all_ok = False
            continue
        out = rr.rerank(item["q"], cands, 4)
        if not any(item["gold"] in f["section"] for f in out):
            all_ok = False
            print(f"    重排后漏: {item['q']} (gold={item['gold']})")
        if item is SPECIAL_Q and out:
            sections = [f["section"] for f in out]
            if "每周例会" not in sections[0]:
                rank = next((i + 1 for i, s in enumerate(sections) if "每周例会" in s), "?")
                print(f"    「每周例会」块排第 {rank}（要求第 1）")
                all_ok = False
    fails += _ok(all_ok, "「每周例会在哪里开？」重排后第 1 名，其余 7 问 gold 仍在 top-4")
    return fails


def step4() -> int:
    print("\n[Step 4] 引用核查")
    fails = 0
    supported = (
        "每周例会在主教学楼 B201 教室召开 [1]。",
        [{"index": 1, "text": "每周例会\n- 时间：每周三晚 19:00–21:00\n- 地点：主教学楼 B201 教室"}],
    )
    unsupported = (
        "单次报销的金额上限是 500 元 [2]。",
        [{"index": 2, "text": "单次报销金额上限 200 元，超过需提前向财务部申请"}],
    )
    r1 = lab_cite.check_citations(*supported)
    fails += _ok(r1.get(1) == "supported", "正确引用 → supported", f"得到 {r1}")
    r2 = lab_cite.check_citations(*unsupported)
    fails += _ok(r2.get(2) == "unsupported", "片段不支持的信息 → unsupported", f"得到 {r2}")
    return fails


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    chunks = demo_chunks()
    pipe = None
    if which in ("2", "3", "all"):
        from memodoc.pipeline import Pipeline

        pipe = Pipeline()
    total = 0
    if which in ("1", "all"):
        total += step1(chunks)
    if which in ("2", "all"):
        total += step2(chunks, pipe)
    if which in ("3", "all"):
        total += step3(pipe)
    if which in ("4", "all"):
        total += step4()
    print(f"\n{'=' * 50}\n结论: {'全部通过 🎉' if total == 0 else f'{total} 项未通过，继续修'}")


if __name__ == "__main__":
    main()
