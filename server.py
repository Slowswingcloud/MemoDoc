"""MemoDoc 学习助手 — 启动入口。

用法：
    开发：python server.py                # 后端 8000 端口（前端另起 npm run dev）
    生产：npm run build 后 python server.py  # FastAPI 同时托管 React 构建产物
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.server:app", host="127.0.0.1", port=8000, reload=False)
