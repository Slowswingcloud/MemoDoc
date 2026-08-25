"""命令行入口：memodoc index / ask / docs / memories。"""
from __future__ import annotations

import argparse
import logging


def main(argv=None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="memodoc", description="MemoDoc 文档问答")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="索引一个文档（PDF/MD/TXT）")
    p_index.add_argument("path")

    p_ask = sub.add_parser("ask", help="提问（非流式）")
    p_ask.add_argument("question")
    p_ask.add_argument("--session", default="cli")
    p_ask.add_argument("--no-memory", action="store_true")

    sub.add_parser("docs", help="列出已索引文档")
    sub.add_parser("memories", help="列出长期记忆")

    p_model = sub.add_parser("download-model", help="下载 embedding 模型到本地（data/models）")
    p_model.add_argument("--force", action="store_true", help="强制重新下载")

    args = parser.parse_args(argv)

    # 延迟导入，避免启动时加载重依赖
    from memodoc.pipeline import Pipeline

    pipe = Pipeline()
    if args.cmd == "index":
        print(pipe.index(args.path))
    elif args.cmd == "ask":
        print(pipe.answer(args.session, args.question, use_memory=not args.no_memory))
    elif args.cmd == "docs":
        print("\n".join(pipe.indexed_docs()) or "(无)")
    elif args.cmd == "memories":
        for f in pipe.list_memories():
            print(f"- [{f['meta'].get('type')}] {f['content']}")
    elif args.cmd == "download-model":
        from memodoc.model import download_model

        download_model(force=args.force)


if __name__ == "__main__":
    main()
