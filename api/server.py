"""MemoDoc — FastAPI 后端服务（React 前端消费）。

角色体系：user / admin（注册登录鉴权）。
能力：会话 / SSE 流式问答（支持检索标签过滤）/ 文档库（全员查看、上传者或管理员可删、
标签增删、下载）/ 打开源文件 / 管理员查看所有用户。
核心 RAG / Memory（src/）零改动；本层只做鉴权与透传。
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from memodoc.config import settings
from memodoc.pipeline import Pipeline

from .auth import auth
from .services import DocService

pipe = Pipeline()
docs_svc = DocService(pipe)

UPLOAD_DIR = settings.data_dir / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

# 首次启动自动创建默认管理员 admin/admin123（若一个账号都没有）
auth.ensure_admin()

app = FastAPI(title="MemoDoc 文档问答 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================= 鉴权依赖 =================
def get_current_user(authorization: str = Header(default="")) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    user = auth.get_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


# ================= 认证 =================
@app.post("/api/auth/register")
def register(payload: dict):
    try:
        return auth.register(
            payload.get("username", ""), payload.get("password", ""), payload.get("role", "user")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/login")
def login(payload: dict):
    try:
        return auth.login(payload.get("username", ""), payload.get("password", ""))
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.post("/api/auth/logout")
def logout(payload: dict, user: dict = Depends(get_current_user)):
    auth.logout(payload.get("token", ""))
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(get_current_user)):
    return user


@app.get("/api/users")
def list_users(_: dict = Depends(require_admin)):
    return auth.list_users()


# ================= 会话（按用户隔离） =================
@app.get("/api/sessions")
def list_sessions(user: dict = Depends(get_current_user)):
    prefix = user["username"] + "_"
    return [s for s in pipe.sessions.list_sessions() if s["id"].startswith(prefix)]


@app.post("/api/sessions")
def new_session(user: dict = Depends(get_current_user)):
    sid = f"{user['username']}_{uuid.uuid4().hex[:8]}"
    return {"session_id": sid}


@app.get("/api/sessions/{sid}")
def get_session(sid: str, _: dict = Depends(get_current_user)):
    return {"messages": pipe.sessions.all(sid)}


@app.delete("/api/sessions/{sid}")
def delete_session(sid: str, _: dict = Depends(get_current_user)):
    pipe.sessions.delete(sid)
    return {"ok": True}


# ================= 聊天（SSE 流式，支持标签过滤） =================
class ChatRequest(BaseModel):
    session_id: str = ""
    question: str
    tags: list[str] = []
    use_memory: bool = True


@app.post("/api/chat")
def chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    def gen():
        def emit(obj: dict):
            yield f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        try:
            username = user["username"]
            sid = req.session_id or f"{username}_{uuid.uuid4().hex[:8]}"
            full = ""
            retrieved = []
            for delta, chunks in pipe.answer_stream(
                sid,
                req.question,
                use_memory=req.use_memory,
                user_id=username,
                tags=req.tags or None,
            ):
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

            checks = pipe.check_citations(full, retrieved) if retrieved else {}
            yield from emit(
                {"type": "checks", "items": [{"index": n, "status": s} for n, s in checks.items()]}
            )
            yield from emit({"type": "done", "session_id": sid})
        except Exception as e:  # noqa: BLE001
            yield from emit({"type": "error", "message": str(e)})
            yield from emit({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream")


# ================= 记忆（按用户隔离） =================
@app.get("/api/memories")
def memories(user: dict = Depends(get_current_user)):
    return pipe.list_memories(user["username"])


@app.delete("/api/memories")
def clear_memories(user: dict = Depends(get_current_user)):
    pipe.clear_memories(user["username"])
    return {"ok": True}


# ================= 文档库 =================
def _find_doc(name: str) -> dict:
    d = next((x for x in docs_svc.list() if x["name"] == name), None)
    if not d:
        raise HTTPException(status_code=404, detail="文档不存在")
    return d


@app.get("/api/documents")
def documents(_: dict = Depends(get_current_user)):
    return docs_svc.list()


@app.get("/api/tags")
def all_tags(_: dict = Depends(get_current_user)):
    return pipe.all_tags()


@app.post("/api/upload")
async def upload(
    files: list[UploadFile],
    tags: str = Form(""),
    user: dict = Depends(get_current_user),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    results = []
    for f in files:
        name = Path(f.filename or "unnamed").name
        dest = UPLOAD_DIR / name
        if dest.exists():
            dest = UPLOAD_DIR / f"{Path(name).stem}_{int(time.time())}{Path(name).suffix}"
        try:
            content = await f.read()
            dest.write_bytes(content)
            r = pipe.index(str(dest), tags=tag_list or None)  # tags 为空时核心自动打标签
            docs_svc.upsert(r["doc"], str(dest), user["username"])
            results.append(
                {
                    "name": name,
                    "doc": r["doc"],
                    "chunks": r["chunks"],
                    "mode": r["mode"],
                    "tags": r.get("tags", []),
                    "ok": True,
                }
            )
        except Exception as e:  # noqa: BLE001
            results.append({"name": name, "ok": False, "error": str(e)})
    return {"results": results}


@app.delete("/api/documents/{name}")
def delete_doc(name: str, user: dict = Depends(get_current_user)):
    d = _find_doc(name)
    if user["role"] != "admin" and d.get("owner") != user["username"]:
        raise HTTPException(status_code=403, detail="仅上传者或管理员可删除")
    pipe.delete_doc(name)
    docs_svc.remove(name)
    return {"ok": True}


# 标签：新增 / 删除
@app.post("/api/documents/{name}/tags")
def add_doc_tag(name: str, payload: dict, _: dict = Depends(get_current_user)):
    tag = (payload.get("tag") or "").strip()
    if not tag:
        raise HTTPException(status_code=400, detail="标签不能为空")
    _find_doc(name)
    pipe.add_doc_tag(name, tag)
    return {"ok": True, "tags": pipe.all_tags()}


@app.delete("/api/documents/{name}/tags/{tag}")
def remove_doc_tag(name: str, tag: str, _: dict = Depends(get_current_user)):
    _find_doc(name)
    pipe.remove_doc_tag(name, tag)
    return {"ok": True, "tags": pipe.all_tags()}


# 下载源文件
@app.get("/api/documents/{name}/download")
def download_doc(name: str, _: dict = Depends(get_current_user)):
    d = _find_doc(name)
    p = Path(d["source"])
    if not p.exists():
        raise HTTPException(status_code=404, detail="源文件不存在")
    return FileResponse(str(p), filename=p.name)


# 打开源文件（点击引用行 → 系统默认程序）
@app.post("/api/open-file")
def open_file(payload: dict, _: dict = Depends(get_current_user)):
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
