"""后端自测（进程内 TestClient，无需起服务）：认证/权限/标签/下载/检索。"""
import json

from fastapi.testclient import TestClient

from api.server import app

c = TestClient(app)


def show(label, r):
    try:
        body = r.json()
    except Exception:
        body = r.text[:100]
    print(f"{label}: {r.status_code} {json.dumps(body, ensure_ascii=False)[:160]}")


# 1) 注册
show("register alice", c.post("/api/auth/register", json={"username": "alice", "password": "alice123", "role": "user"}))
show("register bob", c.post("/api/auth/register", json={"username": "bob", "password": "bob123456", "role": "user"}))
show("register dup", c.post("/api/auth/register", json={"username": "alice", "password": "x" * 8, "role": "user"}))

# 2) 登录
alice = c.post("/api/auth/login", json={"username": "alice", "password": "alice123"}).json()["token"]
bob = c.post("/api/auth/login", json={"username": "bob", "password": "bob123456"}).json()["token"]
admin = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()["token"]
H = lambda t: {"Authorization": f"Bearer {t}"}

# 3) 未登录 401
show("no-auth", c.get("/api/documents"))

# 4) alice 上传（带标签）
with open("data/demo_doc.md", "rb") as f:
    show("upload alice", c.post("/api/upload", headers=H(alice), files={"files": ("demo_alice.md", f, "text/markdown")}, data={"tags": "课程,演示"}))
docs = c.get("/api/documents", headers=H(alice)).json()
d0 = next(d for d in docs if d["name"] == "demo_alice")
print("   owner:", d0["owner"], "tags:", d0["tags"])

# 5) 标签增删（任意用户可改标签）
show("add tag by bob", c.post(f"/api/documents/{d0['name']}/tags", headers=H(bob), json={"tag": "新标签"}))
show("remove tag", c.delete(f"/api/documents/{d0['name']}/tags/%E6%96%B0%E6%A0%87%E7%AD%BE", headers=H(alice)))

# 6) 删除权限
show("bob delete alice doc (403)", c.delete(f"/api/documents/{d0['name']}", headers=H(bob)))
show("alice delete own doc (200)", c.delete(f"/api/documents/{d0['name']}", headers=H(alice)))

# 7) 管理员用户列表 / 普通用户 403
show("admin users", c.get("/api/users", headers=H(admin)))
show("alice users (403)", c.get("/api/users", headers=H(alice)))

# 8) 下载
with open("data/demo_doc.md", "rb") as f:
    r = c.post("/api/upload", headers=H(bob), files={"files": ("dl_test.md", f, "text/markdown")})
doc = r.json()["results"][0]["doc"]
show("download", c.get(f"/api/documents/{doc}/download", headers=H(alice)))

# 9) 带标签检索（SSE）
with c.stream("POST", "/api/chat", headers=H(alice), json={"question": "入社需要什么条件？", "tags": ["课程"]}) as r:
    lines = list(r.iter_lines())
    evts = [ln for ln in lines if ln and ln.startswith("data: ")]
    print("chat sse events:", [json.loads(e[6:])["type"] for e in evts])

print("=== 后端自测完成 ===")
