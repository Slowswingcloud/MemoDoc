"""Embedding 模型下载。

用纯 requests 从 HF 端点直接拉文件到本地普通目录（data/models/），
绕开 huggingface_hub 的缓存与符号链接机制（Windows 无开发者模式时可能受限）。
"""
from __future__ import annotations

import requests

from memodoc.config import settings


def download_model(force: bool = False):
    """把 settings.embed_model 的模型文件下载到 settings.model_dir。"""
    dest = settings.model_dir
    dest.mkdir(parents=True, exist_ok=True)
    repo = settings.embed_model
    endpoint = settings.hf_endpoint.rstrip("/")

    api_url = f"{endpoint}/api/models/{repo}"
    print(f"获取文件清单：{api_url}")
    api = requests.get(api_url, timeout=60)
    api.raise_for_status()
    files = [s["rfilename"] for s in api.json()["siblings"]]
    print(f"共 {len(files)} 个文件")

    for f in files:
        out = dest / f
        if out.exists() and out.stat().st_size > 0 and not force:
            print(f"  跳过（已存在）：{f}")
            continue
        url = f"{endpoint}/{repo}/resolve/main/{f}"
        r = requests.get(url, timeout=600)
        r.raise_for_status()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(r.content)
        print(f"  ✓ {f}（{len(r.content) / 1024:.0f} KB）")

    print(f"完成：模型已下载到 {dest}")
    return dest
