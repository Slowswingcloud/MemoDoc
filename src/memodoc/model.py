"""模型下载：用纯 requests 从 HF 端点拉文件到本地普通目录（绕开缓存/符号链接）。

大文件支持流式写入 + 断点续传（Range）+ 自动重试，应对代理不稳定的长连接。
"""
from __future__ import annotations

import os
from pathlib import Path

import requests

from memodoc.config import settings


def _download_file(url: str, dest: Path, attempts: int = 10) -> None:
    """流式下载单个文件，支持断点续传与重试。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    for attempt in range(1, attempts + 1):
        existing = tmp.stat().st_size if tmp.exists() else 0
        headers = {"Range": f"bytes={existing}-"} if existing else {}
        try:
            with requests.get(url, stream=True, timeout=120, headers=headers) as r:
                if r.status_code == 416:  # 已下载完整
                    os.replace(tmp, dest)
                    return
                r.raise_for_status()
                mode = "ab" if existing and r.status_code == 206 else "wb"
                with open(tmp, mode) as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if chunk:
                            f.write(chunk)
            os.replace(tmp, dest)
            return
        except (requests.exceptions.RequestException, OSError) as e:
            print(
                f"    第 {attempt} 次尝试中断（已下载 {existing // 1024 // 1024} MB）："
                f"{e.__class__.__name__}"
            )
    raise RuntimeError(f"下载失败：{url}")


def download_model(
    repo: str | None = None,
    dest: Path | None = None,
    force: bool = False,
) -> Path:
    """把 repo 的模型文件下载到 dest（默认：embedding 模型）。"""
    repo = repo or settings.embed_model
    dest = dest or settings.model_dir
    dest.mkdir(parents=True, exist_ok=True)
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
        _download_file(url, out)
        print(f"  ✓ {f}（{out.stat().st_size / 1024 / 1024:.1f} MB）")

    print(f"完成：模型已下载到 {dest}")
    return dest


def download_reranker(force: bool = False) -> Path:
    """下载重排模型（默认 bge-reranker-v2-m3）。"""
    return download_model(settings.reranker_model, settings.reranker_dir, force=force)
