"""会话历史：jsonl 持久化，每会话一个文件。"""
from __future__ import annotations

import json
import time
from pathlib import Path

from memodoc.config import settings


class SessionStore:
    def __init__(self):
        self.dir: Path = settings.session_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        safe = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return self.dir / f"{safe or 'default'}.jsonl"

    def append(self, session_id: str, role: str, content: str) -> None:
        with open(self._path(session_id), "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {"role": role, "content": content, "ts": time.time()},
                    ensure_ascii=False,
                )
                + "\n"
            )

    def recent(self, session_id: str, n: int = 6) -> list[dict]:
        return self.all(session_id)[-n:]

    def all(self, session_id: str) -> list[dict]:
        """返回会话完整历史（供前端切换会话时加载）。"""
        p = self._path(session_id)
        if not p.exists():
            return []
        out = []
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                out.append({"role": d["role"], "content": d["content"]})
            except Exception:
                continue
        return out

    def list_sessions(self) -> list[dict]:
        """列出所有会话：{id, title, updated_at}，按最近更新降序。"""
        out = []
        for p in self.dir.glob("*.jsonl"):
            sid = p.stem
            title = "新对话"
            updated = 0.0
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    updated = max(updated, d.get("ts", 0))
                    if title == "新对话" and d.get("role") == "user" and d.get("content"):
                        title = d["content"].strip().replace("\n", " ")[:18]
                except Exception:
                    continue
            out.append({"id": sid, "title": title, "updated_at": updated})
        out.sort(key=lambda x: x["updated_at"], reverse=True)
        return out

    def delete(self, session_id: str) -> None:
        p = self._path(session_id)
        if p.exists():
            p.unlink()

    def reset(self, session_id: str) -> None:
        p = self._path(session_id)
        if p.exists():
            p.unlink()
