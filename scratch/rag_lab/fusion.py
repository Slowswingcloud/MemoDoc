"""Step 2 手搓：向量 + BM25 加权融合。

任务：实现 fuse()，跑通 `python verify.py 2`。
参考：final = w * dense_norm + (1-w) * sparse_norm；各自 min-max 归一化到 [0,1]。
禁止 import memodoc 内部模块。
"""
from __future__ import annotations


def fuse(dense: list[dict], sparse: list[dict], w: float = 0.6) -> list[dict]:
    """把向量召回和 BM25 召回合并。

    输入：两个 list[dict]，每个 dict: {"id","text","section","score"}
    输出：合并后的 list[dict]，按融合分数降序，字段同输入。

    TODO: 实现（按 id 合并；各自 min-max 归一化；加权求和）
    """
    return []
