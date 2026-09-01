"""产品层服务：文档所有权（owner）元数据。

设计约束：只组合现有 pipeline 的【公开接口】或读写数据文件，不修改 src/ 下任何文件。
本层只记录"谁上传了该文档"，供删除权限（仅上传者或管理员）与管理员管理使用。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from memodoc.config import settings
from memodoc.pipeline import Pipeline

DOC_META_PATH = settings.store_dir / "doc_meta.json"


class DocService:
    def __init__(self, pipe: Pipeline):
        self.pipe = pipe
        self.path = DOC_META_PATH
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")

    def upsert(self, doc_name: str, source: str, owner: str) -> None:
        self._data[doc_name] = {"source": source, "owner": owner, "indexed_at": time.time()}
        self._save()

    def remove(self, doc_name: str) -> None:
        self._data.pop(doc_name, None)
        self._save()

    def owner_of(self, doc_name: str) -> str | None:
        return self._data.get(doc_name, {}).get("owner")

    def list(self) -> list[dict]:
        """合并核心注册表（name/source/chunks/tags/tenant/lifecycle）+ 本层 owner。"""
        out = []
        for d in self.pipe.documents():
            meta = self._data.get(d["name"], {})
            out.append(
                {
                    "name": d["name"],
                    "source": d.get("source", ""),
                    "chunks": d.get("chunks", 0),
                    "indexed_at": d.get("indexed_at", meta.get("indexed_at", 0)),
                    "tags": d.get("tags", []),
                    "tenant": d.get("tenant", "default"),
                    "lifecycle": d.get("lifecycle", "active"),
                    "owner": meta.get("owner", ""),
                }
            )
        out.sort(key=lambda x: x.get("indexed_at", 0), reverse=True)
        return out
