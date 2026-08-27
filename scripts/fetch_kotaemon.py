"""临时工具：用断点续传下载 Kotaemon 源码 zip 并解压（沙箱里 git/curl 的 schannel 不可用）。"""
import shutil
import zipfile
from pathlib import Path

from memodoc.model import _download_file

URL = "https://codeload.github.com/Cinnamon/kotaemon/zip/refs/heads/main"
ZIP = Path(".kotaemon.zip")
DEST = Path("kotaemon-ref")


def main():
    if DEST.exists():
        print("kotaemon-ref 已存在，跳过")
        return
    print("下载", URL)
    _download_file(URL, ZIP, attempts=6)
    print(f"已下载 {ZIP.stat().st_size // 1024} KB，解压中…")
    with zipfile.ZipFile(ZIP) as z:
        z.extractall(".")
    extracted = Path("kotaemon-main")
    if extracted.exists():
        shutil.move(str(extracted), str(DEST))
    ZIP.unlink(missing_ok=True)
    print("解压完成 →", DEST)
    core = DEST / "libs" / "kotaemon" / "kotaemon"
    if core.exists():
        print("核心子包：", [p.name for p in core.iterdir() if p.is_dir()])
        ret = core / "retrievals"
        if ret.exists():
            print("retrievals/：", [p.name for p in ret.iterdir() if p.is_file()])


if __name__ == "__main__":
    main()
