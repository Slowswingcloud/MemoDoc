@echo off
rem MemoDoc 学习助手 · 一键启动（生产模式：先 npm run build 一次）
cd /d %~dp0
start "" http://127.0.0.1:8000
.venv\Scripts\python.exe server.py
