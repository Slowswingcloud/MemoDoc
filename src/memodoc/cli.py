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
    p_index.add_argument("--tenant", default=None, help="租户（物理目录 + 虚拟标签）")
    p_index.add_argument("--lifecycle", default=None, help="数据生命周期（active/archive…）")
    p_index.add_argument("--tag", action="append", default=None, help="虚拟标签，可重复传多次")

    p_tag = sub.add_parser("tag", help="管理文档的虚拟标签（增/删/替换/自动）")
    p_tag.add_argument("doc_name")
    p_tag.add_argument("tags", nargs="*", help="替换标签时给出；--add/--remove/--auto 时可为空")
    p_tag.add_argument("--add", action="store_true", help="追加标签")
    p_tag.add_argument("--remove", action="store_true", help="删除标签")
    p_tag.add_argument("--auto", action="store_true", help="自动打标签（LLM 建议 + 启发式兜底）")

    p_auto = sub.add_parser("autotag", help="自动给文档打标签（缺省参数则全部文档）")
    p_auto.add_argument("doc_name", nargs="?", default=None)

    p_re = sub.add_parser("reindex", help="按注册表源路径重新索引（缺省参数则全部；改分块/解析参数后用）")
    p_re.add_argument("doc_name", nargs="?", default=None)

    p_ask = sub.add_parser("ask", help="提问（非流式）")
    p_ask.add_argument("question")
    p_ask.add_argument("--session", default="cli")
    p_ask.add_argument("--no-memory", action="store_true")

    sub.add_parser("docs", help="列出已索引文档")
    sub.add_parser("memories", help="列出长期记忆")

    p_model = sub.add_parser("download-model", help="下载模型到本地（data/models）")
    p_model.add_argument("--force", action="store_true", help="强制重新下载")
    p_model.add_argument("--rerank", action="store_true", help="下载重排模型（默认下载 embedding 模型）")

    args = parser.parse_args(argv)

    # 延迟导入，避免启动时加载重依赖
    from memodoc.pipeline import Pipeline

    pipe = Pipeline()
    if args.cmd == "index":
        print(
            pipe.index(
                args.path,
                tenant=args.tenant,
                lifecycle=args.lifecycle,
                tags=args.tag,
            )
        )
    elif args.cmd == "ask":
        print(pipe.answer(args.session, args.question, use_memory=not args.no_memory))
    elif args.cmd == "docs":
        print("\n".join(pipe.indexed_docs()) or "(无)")
    elif args.cmd == "tag":
        if args.auto:
            print(f"《{args.doc_name}》自动标签：{pipe.auto_tag(args.doc_name)}")
        elif args.add:
            for t in args.tags:
                pipe.add_doc_tag(args.doc_name, t)
            print(f"已追加标签：{args.tags}")
        elif args.remove:
            for t in args.tags:
                pipe.remove_doc_tag(args.doc_name, t)
            print(f"已删除标签：{args.tags}")
        else:
            pipe.set_doc_tags(args.doc_name, args.tags)
            print(f"已设置《{args.doc_name}》标签：{args.tags}")
    elif args.cmd == "autotag":
        if args.doc_name:
            print(f"《{args.doc_name}》自动标签：{pipe.auto_tag(args.doc_name)}")
        else:
            for d in pipe.documents():
                print(f"《{d['name']}》→ {pipe.auto_tag(d['name'])}")
    elif args.cmd == "reindex":
        if args.doc_name:
            print(pipe.reindex(args.doc_name))
        else:
            for d in pipe.documents():
                print(pipe.reindex(d["name"]))
    elif args.cmd == "memories":
        for f in pipe.list_memories():
            print(f"- [{f['meta'].get('type')}] {f['content']}")
    elif args.cmd == "download-model":
        from memodoc.model import download_model, download_reranker

        if args.rerank:
            download_reranker(force=args.force)
        else:
            download_model(force=args.force)


if __name__ == "__main__":
    main()
