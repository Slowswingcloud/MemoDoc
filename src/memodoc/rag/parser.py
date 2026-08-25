"""文档解析：PDF（PyMuPDF）/ Markdown / TXT → 纯文本。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
    import fitz  # PyMuPDF

    doc = fitz.open(p)
    parts = [page.get_text("text") for page in doc]
    doc.close()
    return "\n".join(parts)


def _normalize(text: str) -> str:
    # 统一换行、压掉过多空行
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    return "\n".join(lines).strip()
