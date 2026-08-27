"""安装 jieba：逐文件字节写入 site-packages。

不用 tarfile.extractall（它会把归档里的 unix 权限模式写到 Windows 文件上，
导致沙箱/文件系统权限异常）；改为 extractfile() 读字节 + write_bytes() 直写。
"""
import io
import re
import sys
import tarfile
from pathlib import Path
from urllib.parse import urljoin

import requests

SITE = Path(".venv/Lib/site-packages")
VER = "0.42.1"
INDEX = "https://mirrors.aliyun.com/pypi/simple/jieba/"


def main() -> None:
    idx = requests.get(INDEX, timeout=30).text
    urls = re.findall(r'href="([^"]+)"', idx)
    target = next((u for u in urls if f"jieba-{VER}.tar.gz" in u), None)
    if not target:
        sys.exit(f"镜像上未找到 jieba-{VER} sdist")
    url = urljoin(INDEX, target)
    print("下载", url)
    d = requests.get(url, timeout=180)
    d.raise_for_status()
    n = 0
    with tarfile.open(fileobj=io.BytesIO(d.content), mode="r:gz") as t:
        for m in t.getmembers():
            if not m.isfile() or "/jieba/" not in m.name:
                continue
            rel = m.name.split("/", 1)[1]  # jieba-0.42.1/jieba/... -> jieba/...
            out = SITE / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            f = t.extractfile(m)
            out.write_bytes(f.read() if f else b"")
            n += 1
    print(f"完成：写入 {n} 个文件 → {SITE / 'jieba'}")


if __name__ == "__main__":
    main()
