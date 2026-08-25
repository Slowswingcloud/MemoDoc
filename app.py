"""MemoDoc Gradio Web UI。

功能：文档上传建索引 / 流式问答 / [n] 引用高亮到源面板 / 长期记忆面板 /
「使用长期记忆」开关（用于现场对比「有记忆 vs 无记忆」）/ 清空对话与记忆。
"""
from __future__ import annotations

import html
import re

import gradio as gr

from memodoc.pipeline import Pipeline

pipe = Pipeline()
SESSION_ID = "demo"

_CITE_RE = re.compile(r"\[(\d+)\]")


# ---------- 渲染 ----------
def _esc(text: str) -> str:
    return html.escape(text)


def _cited_ids(text: str) -> set[int]:
    return {int(m) for m in _CITE_RE.findall(text)}


def render_sources(retrieved, cited: set[int]) -> str:
    if not retrieved:
        return "<p style='color:#888'>本轮没有检索到文档片段。</p>"
    cards = []
    for r in retrieved:
        active = r.index in cited
        border = "#f59e0b" if active else "#e5e7eb"
        bg = "#fef9e7" if active else "#ffffff"
        badge = (
            f"<span style='background:#f59e0b;color:#fff;border-radius:999px;"
            f"padding:0 8px;font-weight:600'>[{r.index}]</span>"
        )
        head = (
            f"<div style='color:#6b7280;font-size:12px;margin-bottom:4px'>"
            f"📄 {_esc(r.doc_name)} · {_esc(r.section)}</div>"
        )
        body = f"<div style='font-size:13px;line-height:1.7'>{_esc(r.text)}</div>"
        cards.append(
            f"<div style='border:1.5px solid {border};background:{bg};"
            f"border-radius:10px;padding:10px 12px;margin-bottom:10px'>"
            f"{badge}{head}{body}</div>"
        )
    return "<div>" + "".join(cards) + "</div>"


def render_memories(facts: list[dict]) -> str:
    if not facts:
        return (
            "<p style='color:#888'>还没有记住关于你的事实。<br>"
            "在对话里告诉它你的身份或偏好（例如「我是大一新生」「我喜欢简洁的回答」），"
            "它会在下一轮、下一个会话记住你。</p>"
        )
    cards = []
    for f in facts:
        meta = f.get("meta", {})
        t = meta.get("type", "preference")
        icon = "👤" if t == "identity" else "⭐"
        label = "身份" if t == "identity" else "偏好"
        subject = _esc(meta.get("subject", "其他"))
        cards.append(
            f"<div style='border:1px solid #e5e7eb;border-radius:8px;padding:8px 10px;"
            f"margin-bottom:8px;background:#fafafa'>"
            f"<span style='font-size:12px;color:#6b7280'>{icon} {label} · {subject}</span>"
            f"<div style='font-size:13px;margin-top:2px'>{_esc(f['content'])}</div></div>"
        )
    return "<div>" + "".join(cards) + "</div>"


# ---------- 回调 ----------
def respond(message, chat_history, use_memory, _session):
    chat_history = list(chat_history or [])
    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": ""})

    retrieved = []
    for delta, chunks in pipe.answer_stream(_session, message, use_memory=use_memory):
        chat_history[-1]["content"] += delta
        retrieved = chunks
        cited = _cited_ids(chat_history[-1]["content"])
        yield (
            chat_history,
            render_sources(retrieved, cited),
            render_memories(pipe.list_memories()),
        )

    # 流结束后再刷一次，确保记忆面板包含刚抽取的事实
    cited = _cited_ids(chat_history[-1]["content"])
    yield (
        chat_history,
        render_sources(retrieved, cited),
        render_memories(pipe.list_memories()),
    )


def _on_upload(file, _status):
    if not file:
        return "请先选择文件。"
    try:
        r = pipe.index(file)
        return f"✅ 已索引《{r['doc']}》：{r['chunks']} 块（模式：{r.get('mode', 'embedding')}）"
    except Exception as e:  # noqa: BLE001
        return f"❌ 索引失败：{e}"


def _clear_chat():
    pipe.reset_session(SESSION_ID)
    return [], "对话已清空（长期记忆保留）"


def _clear_memories():
    pipe.clear_memories()
    return render_memories([]), "长期记忆已清空"


# ---------- UI ----------
def build_ui() -> gr.Blocks:
    theme = gr.themes.Soft(primary_hue="orange", secondary_hue="slate")
    with gr.Blocks(title="MemoDoc — 带长期记忆的文档问答", theme=theme) as demo:
        gr.Markdown(
            "# 📚 MemoDoc\n"
            "**带长期记忆的文档问答 Agent** —— 上传文档 → 提问 → 流式回答 + 引用高亮 + 跨会话记忆"
        )

        with gr.Row():
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(type="messages", height=520, label="对话", allow_tags=False)
                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="输入你的问题…（例如：入社需要满足哪些条件？）",
                        show_label=False, scale=4, container=False,
                    )
                    send = gr.Button("发送", variant="primary", scale=1)
                with gr.Row():
                    use_memory = gr.Checkbox(value=True, label="🧠 使用长期记忆")
                    clear_chat = gr.Button("清空对话（保留记忆）", size="sm")
                    clear_mem = gr.Button("清空记忆", size="sm")
                status = gr.Markdown("")

            with gr.Column(scale=2):
                gr.Markdown("### 🔗 引用来源")
                sources = gr.HTML(render_sources([], set()))
                gr.Markdown("### 🧠 长期记忆")
                memories = gr.HTML(render_memories(pipe.list_memories()))

        with gr.Row():
            upload = gr.File(
                label="上传文档（PDF / Markdown / TXT）",
                file_types=[".pdf", ".md", ".markdown", ".txt"],
                type="filepath",
            )
            index_status = gr.Markdown("")

        session_state = gr.State(SESSION_ID)

        send.click(
            respond, [msg, chatbot, use_memory, session_state], [chatbot, sources, memories]
        ).then(lambda: "", None, msg)
        msg.submit(
            respond, [msg, chatbot, use_memory, session_state], [chatbot, sources, memories]
        ).then(lambda: "", None, msg)
        upload.change(_on_upload, [upload, index_status], [index_status])
        clear_chat.click(_clear_chat, None, [chatbot, status])
        clear_mem.click(_clear_memories, None, [memories, status])

    return demo


if __name__ == "__main__":
    build_ui().queue().launch()
