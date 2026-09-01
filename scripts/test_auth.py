"""临时测试：认证 + 权限 + 标签 + 下载 全链路。"""
import json
import os

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")

import requests

BASE = "http://127.0.0.1:8000"


def req(method, path, token=None, **kw):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.request(method, BASE + path, headers=h, **kw, timeout=60)


# 1) 注册两个用户（user + admin）
r = req("POST", "/api/auth/register", json={"username": "alice", "password": "alice123", "role": "user"})
print("register alice:", r.status_code, r.json())
r = req("POST", "/api/auth/register", json={"username": "bob", "password": "bob123456", "role": "user"})
print("register bob:", r.status_code, r.json())

# 2) 登录
r = req("POST", "/api/auth/login", json={"username": "alice", "password": "alice123"})
alice = r.json()["token"]
r = req("POST", "/api/auth/login", json={"username": "admin", "password": "admin123"})
admin = r.json()["token"]
print("login ok, roles:", req("GET", "/api/me", token=alice).json(), "|", req("GET", "/api/me", token=admin).json())

# 3) 未登录访问 -> 401
r = req("GET", "/api/documents")
print("no-auth documents:", r.status_code)

# 4) alice 上传（带标签）
with open("data/demo_doc.md", "rb") as f:
    r = req("POST", "/api/upload", token=alice, files={"files": ("demo_alice.md", f, "text/markdown")}, data={"tags": "课程,演示"})
print("upload alice:", r.status_code, json.dumps(r.json(), ensure_ascii=False)[:150])

# 5) 文档列表（含 owner + tags）
r = req("GET", "/api/documents", token=alice)
docs = r.json()
d0 = next(d for d in docs if d["name"] == "demo_alice")
print("doc owner:", d0["owner"], "tags:", d0["tags"])

# 6) 标签增删
r = req("POST", f"/api/documents/{d0['name']}/tags", token=bob, json={"tag": "新标签"})
print("add tag by bob:", r.status_code)
r = req("DELETE", f"/api/documents/{d0['name']}/tags/{'新标签'}", token=alice)
print("remove tag:", r.status_code)

# 7) 权限：bob 删除 alice 的文档 -> 403；alice 删除 -> 200；admin 任意删
r = req("DELETE", f"/api/documents/{d0['name']}", token=bob)
print("bob delete alice doc:", r.status_code)
r = req("DELETE", f"/api/documents/{d0['name']}", token=alice)
print("alice delete own doc:", r.status_code)

# 8) 管理员查看所有用户
r = req("GET", "/api/users", token=admin)
print("admin users:", json.dumps(r.json(), ensure_ascii=False))
r = req("GET", "/api/users", token=alice)
print("alice users(应403):", r.status_code)

# 9) 下载
with open("data/demo_doc.md", "rb") as f:
    r = req("POST", "/api/upload", token=bob, files={"files": ("dl_test.md", f, "text/markdown")})
doc = r.json()["results"][0]["doc"]
r = req("GET", f"/api/documents/{doc}/download", token=alice)
print("download:", r.status_code, "bytes:", len(r.content))

# 10) 带标签检索（SSE）
r = req("POST", "/api/chat", token=alice, json={"question": "入社需要什么条件？", "tags": ["课程"]}, stream=True)
buf = ""
for line in r.iter_lines(decode_unicode=True):
    if line and line.startswith("data: "):
        buf += line[6:]
        if '"type": "sources"' in line or '"type": "done"' in line or '"type": "error"' in line:
            print("sse:", line[6:][:120])
print("=== auth 全链路测试完成 ===")
