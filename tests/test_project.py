"""MemoDoc 项目级自动化测试（非 RAG 基准评估）。

覆盖：认证 / 权限 / 会话 / 文档库 / 标签 / 下载 / SSE 聊天 / 记忆。
使用 FastAPI TestClient（进程内，无需启动服务），自动生成评测报告 docs/TEST_REPORT.md。

用法：
    .venv\\Scripts\\python.exe tests\\test_project.py
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import time
import unittest
from pathlib import Path

# 保证从任意目录运行时都能 import api / memodoc
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")

from fastapi.testclient import TestClient  # noqa: E402

from api.server import app  # noqa: E402

TS = str(int(time.time()))
U_A = f"tester_a_{TS}"
U_B = f"tester_b_{TS}"
U_PW = "pass123456"
TAG1 = "测试标签"
TAG2 = "单元测试"

client = TestClient(app)
tok_a = tok_b = tok_admin = ""


def H(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# ---------------- 认证 ----------------
class TestAuth(unittest.TestCase):
    def test_010_register_ok(self):
        r = client.post("/api/auth/register", json={"username": U_A, "password": U_PW, "role": "user"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["role"], "user")

    def test_020_register_dup(self):
        r = client.post("/api/auth/register", json={"username": U_A, "password": U_PW})
        self.assertEqual(r.status_code, 400)

    def test_030_register_short_username(self):
        r = client.post("/api/auth/register", json={"username": "x", "password": U_PW})
        self.assertEqual(r.status_code, 400)

    def test_040_register_short_password(self):
        r = client.post("/api/auth/register", json={"username": f"pw_{TS}", "password": "123"})
        self.assertEqual(r.status_code, 400)

    def test_050_register_bad_role(self):
        r = client.post("/api/auth/register", json={"username": f"role_{TS}", "password": U_PW, "role": "root"})
        self.assertEqual(r.status_code, 400)

    def test_060_login_ok(self):
        global tok_a, tok_b, tok_admin
        tok_a = client.post("/api/auth/login", json={"username": U_A, "password": U_PW}).json()["token"]
        client.post("/api/auth/register", json={"username": U_B, "password": U_PW, "role": "user"})
        tok_b = client.post("/api/auth/login", json={"username": U_B, "password": U_PW}).json()["token"]
        r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(r.status_code, 200)
        tok_admin = r.json()["token"]

    def test_070_login_wrong_password(self):
        r = client.post("/api/auth/login", json={"username": U_A, "password": "wrong!"})
        self.assertEqual(r.status_code, 401)

    def test_080_no_auth_401(self):
        self.assertEqual(client.get("/api/documents").status_code, 401)

    def test_090_invalid_token_401(self):
        self.assertEqual(client.get("/api/documents", headers=H("bad_token")).status_code, 401)

    def test_100_admin_users_ok(self):
        r = client.get("/api/users", headers=H(tok_admin))
        self.assertEqual(r.status_code, 200)
        self.assertIn(U_A, [u["username"] for u in r.json()])

    def test_110_user_users_403(self):
        self.assertEqual(client.get("/api/users", headers=H(tok_a)).status_code, 403)


# ---------------- 会话 ----------------
class TestSessions(unittest.TestCase):
    def test_010_new_session_prefix(self):
        r = client.post("/api/sessions", headers=H(tok_a))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["session_id"].startswith(U_A + "_"))

    def test_020_session_isolation(self):
        sa = {s["id"] for s in client.get("/api/sessions", headers=H(tok_a)).json()}
        sb = {s["id"] for s in client.get("/api/sessions", headers=H(tok_b)).json()}
        self.assertTrue(sa.isdisjoint(sb))

    def test_030_get_delete_session(self):
        sid = client.post("/api/sessions", headers=H(tok_a)).json()["session_id"]
        r = client.get(f"/api/sessions/{sid}", headers=H(tok_a))
        self.assertEqual(r.status_code, 200)
        self.assertIn("messages", r.json())
        self.assertEqual(client.delete(f"/api/sessions/{sid}", headers=H(tok_a)).status_code, 200)


# ---------------- 文档库 ----------------
class TestDocuments(unittest.TestCase):
    DOC = "data/demo_doc.md"

    def test_010_upload_with_tags(self):
        with open(self.DOC, "rb") as f:
            r = client.post(
                "/api/upload", headers=H(tok_a),
                files={"files": (f"tagtest_{TS}.md", f, "text/markdown")},
                data={"tags": f"{TAG1},{TAG2}"},
            )
        self.assertEqual(r.status_code, 200)
        res = r.json()["results"][0]
        self.assertTrue(res["ok"])
        self.assertEqual(res["tags"], [TAG1, TAG2])

    def test_020_upload_auto_tag(self):
        with open(self.DOC, "rb") as f:
            r = client.post(
                "/api/upload", headers=H(tok_a), files={"files": (f"autotag_{TS}.md", f, "text/markdown")}
            )
        res = r.json()["results"][0]
        self.assertTrue(res["ok"])
        self.assertGreater(len(res.get("tags", [])), 0)

    def test_030_doc_list_has_owner_tags(self):
        docs = client.get("/api/documents", headers=H(tok_a)).json()
        d = next((x for x in docs if x["name"] == f"tagtest_{TS}"), None)
        self.assertIsNotNone(d)
        self.assertEqual(d["owner"], U_A)
        self.assertIn(TAG2, d["tags"])

    def test_040_tag_add_remove(self):
        name = f"tagtest_{TS}"
        r = client.post(f"/api/documents/{name}/tags", headers=H(tok_b), json={"tag": "临时标签"})
        self.assertEqual(r.status_code, 200)
        docs = client.get("/api/documents", headers=H(tok_a)).json()
        self.assertIn("临时标签", next(x for x in docs if x["name"] == name)["tags"])
        r = client.delete(f"/api/documents/{name}/tags/%E4%B8%B4%E6%97%B6%E6%A0%87%E7%AD%BE", headers=H(tok_a))
        self.assertEqual(r.status_code, 200)

    def test_050_delete_by_other_403(self):
        self.assertEqual(client.delete(f"/api/documents/tagtest_{TS}", headers=H(tok_b)).status_code, 403)

    def test_060_delete_by_owner_ok(self):
        self.assertEqual(client.delete(f"/api/documents/tagtest_{TS}", headers=H(tok_a)).status_code, 200)

    def test_070_admin_delete_any(self):
        with open(self.DOC, "rb") as f:
            name = client.post(
                "/api/upload", headers=H(tok_b), files={"files": (f"admintest_{TS}.md", f, "text/markdown")}
            ).json()["results"][0]["doc"]
        self.assertEqual(client.delete(f"/api/documents/{name}", headers=H(tok_admin)).status_code, 200)

    def test_080_download_ok(self):
        with open(self.DOC, "rb") as f:
            name = client.post(
                "/api/upload", headers=H(tok_b), files={"files": (f"dl_{TS}.md", f, "text/markdown")}
            ).json()["results"][0]["doc"]
        r = client.get(f"/api/documents/{name}/download", headers=H(tok_a))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content[:30], Path(self.DOC).read_bytes()[:30])

    def test_090_download_not_found(self):
        self.assertEqual(client.get("/api/documents/%E4%B8%8D%E5%AD%98%E5%9C%A8/download", headers=H(tok_a)).status_code, 404)

    def test_100_multi_upload(self):
        with open(self.DOC, "rb") as f1, open(self.DOC, "rb") as f2:
            r = client.post(
                "/api/upload", headers=H(tok_a),
                files=[("files", (f"multi_{TS}_1.md", f1, "text/markdown")), ("files", (f"multi_{TS}_2.md", f2, "text/markdown"))],
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["results"]), 2)


# ---------------- 聊天（SSE） ----------------
class TestChat(unittest.TestCase):
    def test_010_no_auth_401(self):
        self.assertEqual(client.post("/api/chat", json={"question": "你好", "tags": []}).status_code, 401)

    def _sse(self, **payload):
        with client.stream("POST", "/api/chat", headers=H(tok_a), json=payload, timeout=180) as r:
            lines = list(r.iter_lines())
        return [json.loads(l[6:]) for l in lines if l and l.startswith("data: ")]

    def test_020_sse_flow(self):
        evts = self._sse(question="加入极客社需要满足哪些条件？", tags=[], session_id="")
        types = [e["type"] for e in evts]
        self.assertIn("sources", types)
        self.assertIn("delta", types)
        self.assertIn("done", types)
        answer = "".join(e.get("text", "") for e in evts if e["type"] == "delta")
        self.assertGreater(len(answer), 10)
        sid = next((e["session_id"] for e in evts if e["type"] == "done" and e.get("session_id")), None)
        self.assertTrue(sid and sid.startswith(U_A + "_"))

    def test_030_tag_filter(self):
        evts = self._sse(question="极客社的积分有什么用？", tags=[TAG2], session_id="")
        types = [e["type"] for e in evts]
        self.assertNotIn("error", types)
        self.assertIn("done", types)


# ---------------- 记忆 ----------------
class TestMemory(unittest.TestCase):
    def test_010_memory_after_chat(self):
        with client.stream(
            "POST", "/api/chat", headers=H(tok_a),
            json={"question": "我是大一新生，刚加入极客社。", "tags": [], "session_id": ""},
            timeout=180,
        ) as r:
            list(r.iter_lines())
        mems = client.get("/api/memories", headers=H(tok_a)).json()
        self.assertGreater(len(mems), 0)


# ---------------- 运行器 + 报告 ----------------
def _collect():
    loader = unittest.TestLoader()
    cases = []
    for cls in (TestAuth, TestSessions, TestDocuments, TestChat, TestMemory):
        cases.extend(loader.loadTestsFromTestCase(cls))
    return cases


def _cleanup():
    """清理测试上传的文档（保留演示数据干净）。"""
    try:
        docs = client.get("/api/documents", headers=H(tok_admin)).json()
        for d in docs:
            if f"_{TS}" in d["name"] or d["name"].startswith(("tagtest", "autotag", "multi", "dl_", "admintest")):
                client.delete(f"/api/documents/{d['name']}", headers=H(tok_admin))
    except Exception:
        pass


def main():
    cases = _collect()
    rows: list[dict] = []
    mod = {"TestAuth": "认证", "TestSessions": "会话", "TestDocuments": "文档库", "TestChat": "聊天(SSE)", "TestMemory": "记忆"}
    print(f"共 {len(cases)} 条用例\n")
    for t in cases:
        cls = t.__class__.__name__
        name = f"{cls}.{t._testMethodName}"
        try:
            t.setUp()
            try:
                getattr(t, t._testMethodName)()
                rows.append({"module": cls, "name": name, "status": "PASS", "detail": ""})
                print(f"  ✓ {name}")
            except unittest.SkipTest as e:
                rows.append({"module": cls, "name": name, "status": "SKIP", "detail": str(e)})
                print(f"  - {name}: SKIP {e}")
            except Exception as e:  # noqa: BLE001
                rows.append({"module": cls, "name": name, "status": "FAIL", "detail": str(e)})
                print(f"  ✗ {name}: {e}")
            finally:
                t.tearDown()
        except Exception as e:  # noqa: BLE001
            rows.append({"module": cls, "name": name, "status": "ERROR", "detail": str(e)})
            print(f"  ! {name}: {e}")

    _cleanup()
    _write_report(rows)

    total = len(rows)
    passed = sum(1 for r in rows if r["status"] == "PASS")
    print(f"\n{'=' * 50}\n通过 {passed}/{total} = {passed / total:.0%}")


def _write_report(rows: list[dict]):
    mod_names = {"TestAuth": "认证", "TestSessions": "会话", "TestDocuments": "文档库", "TestChat": "聊天(SSE)", "TestMemory": "记忆"}
    total = len(rows)
    passed = sum(1 for r in rows if r["status"] == "PASS")
    failed = total - passed
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "# MemoDoc 项目评测报告",
        "",
        f"- 生成时间：{now}",
        "- 测试方式：FastAPI TestClient（进程内，未启动服务）",
        "- 测试范围：认证 / 权限 / 会话 / 文档库 / 标签 / 下载 / SSE 聊天 / 记忆（**不含 RAG 基准评估**）",
        "",
        "## 汇总",
        "",
        f"**通过 {passed} / {total}（{passed / total:.0%}）**，失败 {failed}。",
        "",
        "| 模块 | 用例数 | 通过 | 失败 | 通过率 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for cls, label in mod_names.items():
        m = [r for r in rows if r["module"] == cls]
        p = sum(1 for r in m if r["status"] == "PASS")
        lines.append(f"| {label} | {len(m)} | {p} | {len(m) - p} | {p / max(len(m), 1):.0%} |")

    lines += ["", "## 用例明细"]
    cur = None
    for r in rows:
        label = mod_names.get(r["module"], r["module"])
        if label != cur:
            lines.append(f"\n### {label}")
            cur = label
        mark = "✅" if r["status"] == "PASS" else ("⚠️" if r["status"] == "SKIP" else "❌")
        detail = f" — {r['detail']}" if r["detail"] else ""
        lines.append(f"- {mark} `{r['name']}` {r['status']}{detail}")

    lines += ["", "## 结论", ""]
    if failed == 0:
        lines.append("全部用例通过，项目功能符合预期（登录鉴权、角色权限、会话隔离、文档上传/删除权限、标签管理、下载、SSE 问答、记忆均正常）。")
    else:
        lines.append(f"共 {failed} 条用例未通过，详见上方明细。")
    lines.append("")
    lines.append("> 说明：测试过程会注册临时账号并上传/删除临时文档，已自动清理；RAG 检索质量指标不在本报告范围。")

    out = Path(__file__).resolve().parents[1] / "docs" / "TEST_REPORT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n评测报告已生成：{out}")


if __name__ == "__main__":
    main()
