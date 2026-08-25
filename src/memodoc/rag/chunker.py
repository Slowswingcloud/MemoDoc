"""标题感知分块：先按 Markdown 标题切段，段内再按长度滑窗（带重叠）。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


@dataclass
class Chunk:
    id: str
    text: str
    doc_name: str
    section_path: str
    meta: dict = field(default_factory=dict)


def chunk_text(
    text: str,
    doc_name: str,
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[Chunk]:
    blocks = _split_by_headings(text)
    chunks: list[Chunk] = []
    idx = 0
    for section_path, block_text in blocks:
        for seg in _windows(block_text, chunk_size, overlap):
            chunks.append(
                Chunk(
                    id=f"{doc_name}#{idx:03d}",
                    text=seg,
                    doc_name=doc_name,
                    section_path=section_path,
                    meta={"section": section_path},
                )
            )
            idx += 1
    return chunks


def _split_by_headings(text: str) -> list[tuple[str, str]]:
    lines = text.split("\n")
    blocks: list[tuple[str, str]] = []
    cur_path: list[str] = []
    cur_lines: list[str] = []

    def flush() -> None:
        nonlocal cur_lines
        if any(ln.strip() for ln in cur_lines):
            blocks.append((" / ".join(cur_path) or "正文", "\n".join(cur_lines)))
        cur_lines = []

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            cur_path = (cur_path[: level - 1] + [title])[:3]
        else:
            if line.strip() or cur_lines:
                cur_lines.append(line)
    flush()
    return blocks


def _windows(text: str, size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    step = max(size - overlap, 1)
    return [text[i : i + size] for i in range(0, len(text), step) if text[i : i + size].strip()]
