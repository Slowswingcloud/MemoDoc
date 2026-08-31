"""文档解析：PDF（PyMuPDF，块级提取 + 连字符断行修复）/ Markdown / TXT → 纯文本。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# 连字符断行：eluci-\ndating → elucidating（仅字母-字母，中文不受影响）
_HYPHEN_EOL = re.compile(r"([a-zA-Z])-\s*\n\s*([a-zA-Z])")


@dataclass
class ParsedDocument:
    name: str
    text: str
    source_path: str


def parse_file(path: str | Path) -> ParsedDocument:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在：{p}")
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        text = _parse_pdf(p)
    else:
        text = _parse_text(p)
    text = _normalize(text)
    return ParsedDocument(name=p.stem, text=text, source_path=str(p))


def _parse_text(p: Path) -> str:
    data = p.read_bytes()
    for enc in ("utf-8", "gbk", "utf-16"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_pdf(p: Path) -> str:
    """块级提取：按坐标排序保证阅读顺序（改善双栏 PDF），再修复连字符断行。

    借鉴 Kotaemon 的 Docling 思路的轻量版；复杂版面仍建议上 docling。
    """
    import fitz  # PyMuPDF

    doc = fitz.open(p)
    page_texts = []
    for page in doc:
        blocks = page.get_text("blocks")
        # block_type==0 为文本块；按 (y0, x0) 排序（自上而下、从左到右）
        texts = sorted(
            (b for b in blocks if len(b) >= 7 and b[6] == 0),
            key=lambda b: (round(b[1], 1), b[0]),
        )
        page_texts.append("\n".join(t[4].strip() for t in texts if t[4].strip()))
    doc.close()
    return "\n".join(page_texts)


def _normalize(text: str) -> str:
    # 统一换行、压掉过多空行
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 连字符断行修复（放在换行统一之后）
    text = _HYPHEN_EOL.sub(r"\1\2", text)
    lines = [ln.rstrip() for ln in text.split("\n")]
    return "\n".join(lines).strip()
