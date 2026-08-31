"""临时测试：上传分类 + 画像 + 统计。"""
import json
import os

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")

import requests

BASE = "http://127.0.0.1:8000"

# 1) 上传（带课程/类型分类）
files = [("files", ("demo_doc.md", open("data/demo_doc.md", "rb"), "text/markdown"))]
r = requests.post(f"{BASE}/api/upload", files=files, data={"course": "软件工程", "doc_type": "课件"}, timeout=120)
print("upload:", json.dumps(r.json(), ensure_ascii=False)[:200])

# 2) 文档列表（按课程过滤）
r = requests.get(f"{BASE}/api/documents", params={"course": "软件工程"}, timeout=30)
docs = r.json()
print("documents(软件工程):", [(d["name"], d["course"], d["doc_type"]) for d in docs][:3])

# 3) 课程列表
r = requests.get(f"{BASE}/api/courses", timeout=30)
print("courses:", r.json())

# 4) 画像 / 统计
r = requests.get(f"{BASE}/api/profile", params={"user_id": "张三"}, timeout=30)
print("profile:", json.dumps(r.json(), ensure_ascii=False)[:200])
r = requests.get(f"{BASE}/api/stats", timeout=30)
print("stats:", json.dumps(r.json(), ensure_ascii=False)[:200])
