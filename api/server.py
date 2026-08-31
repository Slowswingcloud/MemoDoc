"""MemoDoc 学习助手 — FastAPI 后端服务（React 前端消费）。

只调用现有 pipeline / 服务的公开接口；RAG 与 Memory 核心逻辑未做任何修改。
提供：会话 / SSE 流式问答 / 引用核查 / 文档库分类 / 上传 / 学习画像 / 班级统计 / 打开源文件。
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from memodoc.config import settings
from memodoc.pipeline import Pipeline

from .services import DocService, LearningService

pipe = Pipeline()
docs_svc = DocService(pipe)
learn_svc = LearningService(pipe)

UPLOAD_DIR = settings.data_dir / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

ROLE_PREFIX = {"student": "stu", "teacher": "tea"}

app = FastAPI(title="MemoDoc 学习助手 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _user_id(role: str, name: str | None = None) -> str:
    if role == "teacher":
        return "tea"
    return (name or "student").strip() or "student"


# ================= 会话 =================
@app.get("/api/sessions")
def list_sessions(role: str = "student"):
    prefix = ROLE_PREFIX.get(role, "stu") + "_"
    return [s for s in pipe.sessions.list_sessions() if s["id"].startswith(prefix)]


@app.post("/api/sessions")
def new_session(role: str = "student"):
    sid = f"{ROLE_PREFIX.get(role, 'stu')}_{uuid.uuid4().hex[:8]}"
    return {"session_id": sid}


@app.get("/api/sessions/{sid}")
def get_session(sid: str):
    return {"messages": pipe.sessions.all(sid)}


@app.delete("/api/sessions/{sid}")
def delete_session(sid: str):
    pipe.sessions.delete(sid)
    return {"ok": True}


# ================= 聊天（SSE 流式） =================
class ChatRequest(BaseModel):
    session_id: str = ""
    question: str
    role: str = "student"
    user_id: str = "student"
    use_memory: bool = True


@app.post("/api/chat")
def chat(req: ChatRequest):
    def gen():
        def emit(obj: dict):
            yield f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        try:
            uid = _user_id(req.role, req.user_id)
            sid = req.session_id or f"{ROLE_PREFIX.get(req.role, 'stu')}_{uuid.uuid4().hex[:8]}"
            full = ""
            retrieved = []
            for delta, chunks in pipe.answer_stream(sid, req.question, use_memory=req.use_memory, user_id=uid):
                if not retrieved:
                    yield from emit(
                        {
                            "type": "sources",
                            "items": [
                                {
                                    "index": r.index,
                                    "doc_name": r.doc_name,
                                    "section": r.section,
                                    "source": r.source,
                                    "preview": r.text.replace("\n", " ")[:60],
                                }
                                for r in chunks
                            ],
                        }
                    )
                    retrieved = chunks
                full += delta
                yield from emit({"type": "delta", "text": delta})

            # 引用核查 + 学习画像抽取
            checks = pipe.check_citations(full, retrieved) if retrieved else {}
            yield from emit({"type": "checks", "items": [{"index": n, "status": s} for n, s in checks.items()]})
            if req.role == "student":
                learn_svc.extract(req.question, full, uid)
            yield from emit({"type": "done", "session_id": sid})
        except Exception as e:  # noqa: BLE001
            yield from emit({"type": "error", "message": str(e)})
            yield from emit({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream")


# ================= 记忆 / 学习画像 / 班级统计 =================
@app.get("/api/memories")
def memories(user_id: str = "student"):
    return pipe.list_memories(user_id)


@app.delete("/api/memories")
def clear_memories(user_id: str = "student"):
    pipe.clear_memories(user_id)
    return {"ok": True}


@app.get("/api/profile")
def profile(user_id: str = "student"):
    return learn_svc.profile(user_id)


@app.get("/api/stats")
def stats():
    return learn_svc.class_stats()


# ================= 文档库 =================
@app.get("/api/documents")
def documents(course: str | None = None, doc_type: str | None = None):
    return docs_svc.list(course, doc_type)


@app.get("/api/courses")
def courses():
    return docs_svc.courses()


@app.post("/api/upload")
async def upload(
    files: list[UploadFile],
    course: str = Form("默认课程"),
    doc_type: str = Form("课件"),
):
    results = []
    for f in files:
        name = Path(f.filename or "unnamed").name
        dest = UPLOAD_DIR / name
        if dest.exists():
            dest = UPLOAD_DIR / f"{Path(name).stem}_{int(time.time())}{Path(name).suffix}"
        try:
            content = await f.read()
            dest.write_bytes(content)
            r = pipe.index(str(dest))
            docs_svc.upsert(r["doc"], str(dest), course, doc_type, r["chunks"])
            results.append({"name": name, "doc": r["doc"], "chunks": r["chunks"], "mode": r["mode"], "ok": True})
        except Exception as e:  # noqa: BLE001
            results.append({"name": name, "ok": False, "error": str(e)})
    return {"results": results}


@app.delete("/api/documents/{name}")
def delete_doc(name: str):
    pipe.delete_doc(name)
    docs_svc.remove(name)
    return {"ok": True}


# ================= 打开源文件（点击引用行 → 系统默认程序） =================
@app.post("/api/open-file")
def open_file(payload: dict):
    path = payload.get("path", "")
    try:
        p = Path(path).resolve()
        allowed = [str(UPLOAD_DIR.resolve()), str(settings.data_dir.resolve())]
        if not any(str(p).startswith(a) for a in allowed):
            return {"ok": False, "message": "路径不在允许范围"}
    except Exception:
        return {"ok": False, "message": "非法路径"}
    if not p.exists():
        return {"ok": False, "message": "文件不存在"}
    if os.name == "nt":
        os.startfile(str(p))
    return {"ok": True, "message": f"已打开 {p.name}"}


# ================= 静态托管（React 构建产物） =================
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
