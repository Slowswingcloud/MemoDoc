"""临时测试：POST /api/chat，读取 SSE 事件流。"""
import json
import os
import sys

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

import requests

url = "http://127.0.0.1:8000/api/chat"
payload = {
    "question": "什么是软件过程模型？",
    "role": "student",
    "user_id": "张三",
    "session_id": "",
    "use_memory": True,
}
print("POST", url, flush=True)
r = requests.post(url, json=payload, stream=True, timeout=180)
print("status:", r.status_code, flush=True)
for line in r.iter_lines(decode_unicode=True):
    if not line or not line.startswith("data: "):
        continue
    try:
        evt = json.loads(line[6:])
    except Exception:
        continue
    t = evt.get("type")
    if t == "delta":
        sys.stdout.write(evt.get("text", ""))
        sys.stdout.flush()
    elif t == "sources":
        print("\n[sources]", len(evt.get("items", [])), "项", flush=True)
        for it in evt.get("items", [])[:3]:
            print("   ", it["index"], it["doc_name"], "|", it["section"], flush=True)
    elif t == "checks":
        print("[checks]", evt.get("items"), flush=True)
    elif t == "done":
        print("[done] session_id =", evt.get("session_id"), flush=True)
    elif t == "error":
        print("[error]", evt.get("message"), flush=True)
print("\n=== SSE 测试完成 ===", flush=True)
