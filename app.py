"""MemoDoc Gradio Web UI（v3，前端风格完全参考 GPT-Gradio-Agent）。

布局（对应其 .col-container 三列网格 1fr 2.5fr 1fr）：
- 左侧：会话栏（历史）—— 图标按钮「新对话/删除会话」+ Radio 会话列表（CSS 列表化）
- 中间：对话主区 —— Tabs「对话 / 文档库」（聊天流式、批量上传、文档库检索）
- 右侧：引用来源 + 长期记忆 面板（Tabs + Accordion，点击引用行可直接打开源文件）
"""
from __future__ import annotations

import datetime
import html
import os
import re
import shutil
import time
import uuid
import warnings
from pathlib import Path

import gradio as gr

from memodoc.config import settings
from memodoc.pipeline import Pipeline

# Gradio 5.x 的几条误发/良性弃用警告（css/show_copy_button 在 5.50 仍有效），静默掉噪音
warnings.filterwarnings("ignore", message="The default value of 'allow_tags'")
warnings.filterwarnings("ignore", message="The 'css' parameter in the Blocks constructor")
warnings.filterwarnings("ignore", message="The 'show_copy_button' parameter")

pipe = Pipeline()
UPLOAD_DIR = settings.data_dir / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_CITE_RE = re.compile(r"\[(\d+)\]")


# ================= 主题（复刻 GPT-Gradio-Agent 的 adjust_theme） =================
def _adjust_theme():
    set_theme = gr.themes.Soft(
        primary_hue=gr.themes.utils.colors.blue,
        neutral_hue=gr.themes.utils.colors.gray,
        font=["sans-serif", "Microsoft YaHei", "ui-sans-serif", "system-ui", "sans-serif"],
        font_mono=["ui-monospace", "Consolas", "monospace"],
    )
    set_theme.set(
        # Transition
        button_transition="none",
        # Shadows（Gradio 5.50 已移除 button_shadow*，保留其余）
        input_shadow="0 0 0 *shadow_spread transparent, *shadow_inset",
        input_shadow_focus="0 0 0 *shadow_spread *secondary_50, *shadow_inset",
        input_shadow_focus_dark="0 0 0 *shadow_spread *neutral_700, *shadow_inset",
        checkbox_label_shadow="*shadow_drop",
        block_shadow="*shadow_drop",
        form_gap_width="1px",
        # Button borders
        input_border_width="1px",
        input_background_fill="white",
        # Gradients
        stat_background_fill="linear-gradient(to right, *primary_400, *primary_200)",
        stat_background_fill_dark="linear-gradient(to right, *primary_400, *primary_600)",
        checkbox_label_background_fill="linear-gradient(to top, *neutral_50, white)",
        checkbox_label_background_fill_dark="linear-gradient(to top, *neutral_900, *neutral_800)",
        checkbox_label_background_fill_hover="linear-gradient(to top, *neutral_100, white)",
        checkbox_label_background_fill_hover_dark="linear-gradient(to top, *neutral_900, *neutral_800)",
        button_primary_background_fill="linear-gradient(to bottom right, *primary_150, *primary_350)",
        button_primary_background_fill_dark="linear-gradient(to bottom right, *primary_500, *primary_600)",
        button_primary_background_fill_hover="linear-gradient(to bottom right, *primary_100, *primary_200)",
        button_primary_background_fill_hover_dark="linear-gradient(to bottom right, *primary_500, *primary_500)",
        button_primary_border_color_dark="*primary_500",
        button_secondary_background_fill="linear-gradient(to bottom right, *neutral_100, *neutral_200)",
        button_secondary_background_fill_dark="linear-gradient(to bottom right, *neutral_600, *neutral_700)",
        button_secondary_background_fill_hover="linear-gradient(to bottom right, *neutral_100, *neutral_100)",
        button_secondary_background_fill_hover_dark="linear-gradient(to bottom right, *neutral_600, *neutral_600)",
    )
    return set_theme


# ================= 工具 =================
def _esc(t: str) -> str:
    return html.escape(t)


def _fmt_time(ts: float) -> str:
    if not ts:
        return ""
    dt = datetime.datetime.fromtimestamp(ts)
    if dt.date() == datetime.date.today():
        return dt.strftime("%H:%M")
    return dt.strftime("%m-%d %H:%M")


def _cited_ids(text: str) -> set[int]:
    return {int(m) for m in _CITE_RE.findall(text)}


def _open_file(path: str) -> str:
    """用系统默认程序打开源文件（Windows 下 os.startfile）。"""
    if not path or not Path(path).exists():
        return f"文件不存在：{path}"
    if os.name == "nt":
        os.startfile(path)
        return f"📂 已打开：{Path(path).name}"
    return f"源文件：{path}"


# ================= 渲染 =================
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


def _sources_rows(retrieved, cited: set[int], checks: dict) -> list[list]:
    rows = []
    for r in retrieved:
        mark = ""
        if checks.get(r.index) == "supported":
            mark = "✓ 已核查"
        elif checks.get(r.index) == "unsupported":
            mark = "⚠ 不支持"
        rows.append(
            [f"[{r.index}]", r.doc_name, r.section, r.text.replace("\n", " ")[:50], mark]
        )
    return rows


def _radio_update(sessions: list[dict], active_sid: str | None = None) -> gr.update:
    """把会话列表渲染成 Radio 的 choices/value（对应 CSS #history-select-dropdown）。"""
    titles = [s["title"] for s in sessions]
    value = None
    if active_sid:
        value = next((s["title"] for s in sessions if s["id"] == active_sid), None)
    if value is None and titles:
        value = titles[0]
    return gr.update(choices=titles, value=value)


# ================= 会话管理 =================
def _new_session() -> tuple:
    sid = uuid.uuid4().hex[:8]
    sessions = pipe.sessions.list_sessions()
    return sid, [], _radio_update(sessions, sid), "已创建新对话（跨会话记忆保留）"


def _switch_session(evt: gr.SelectData) -> tuple:
    title = evt.value
    sessions = pipe.sessions.list_sessions()
    sid = next((s["id"] for s in sessions if s["title"] == title), None)
    if not sid:
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
    history = [{"role": m["role"], "content": m["content"]} for m in pipe.sessions.all(sid)]
    return sid, history, gr.update(value=[]), render_memories(pipe.list_memories()), f"已切换到会话「{title}」"


def _delete_session(current_session) -> tuple:
    if current_session:
        pipe.sessions.delete(current_session)
    sessions = pipe.sessions.list_sessions()
    sid = sessions[0]["id"] if sessions else None
    history = (
        [{"role": m["role"], "content": m["content"]} for m in pipe.sessions.all(sid)]
        if sid else []
    )
    return sid, history, _radio_update(sessions, sid), "已删除当前会话"


def _clear_chat(sid) -> tuple:
    if sid:
        pipe.sessions.reset(sid)
    sessions = pipe.sessions.list_sessions()
    return [], _radio_update(sessions, sid), "对话已清空（长期记忆保留）"


def _clear_mem() -> tuple:
    pipe.clear_memories()
    return render_memories([]), "长期记忆已清空"


# ================= 问答 =================
def respond(message, chat_history, use_memory, session_id, scope_tags):
    chat_history = list(chat_history or [])
    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": ""})

    # 第一帧：用户消息立即上屏 + 输入框立即清空（不等检索/生成）
    yield (
        chat_history,
        gr.update(value=[]),
        render_memories(pipe.list_memories()),
        "",
        gr.update(),
        gr.update(),
        "🔍 正在检索文档…",
        gr.update(),
    )

    sid = session_id or uuid.uuid4().hex[:8]
    retrieved = []
    try:
        for delta, chunks in pipe.answer_stream(
            sid, message, use_memory=use_memory, tags=scope_tags or None
        ):
            chat_history[-1]["content"] += delta
            retrieved = chunks
            cited = _cited_ids(chat_history[-1]["content"])
            yield (
                chat_history,
                gr.update(value=_sources_rows(retrieved, cited, {})),
                render_memories(pipe.list_memories()),
                "",
                gr.update(),
                gr.update(),
                gr.update(),
                retrieved,
            )

        # 流结束：引用核查 + 刷新会话列表
        cited = _cited_ids(chat_history[-1]["content"])
        checks = {}
        if retrieved:
            try:
                checks = pipe.check_citations(chat_history[-1]["content"], retrieved)
            except Exception:
                checks = {}
        sessions = pipe.sessions.list_sessions()
        yield (
            chat_history,
            gr.update(value=_sources_rows(retrieved, cited, checks)),
            render_memories(pipe.list_memories()),
            "",
            _radio_update(sessions, sid),
            sid,
            "✅ 回答完成",
            retrieved,
        )
    except Exception as e:  # noqa: BLE001
        chat_history[-1]["content"] = f"⚠️ 出错了：{e}"
        yield (
            chat_history,
            gr.update(value=[]),
            render_memories(pipe.list_memories()),
            "",
            gr.update(),
            gr.update(),
            f"❌ {e}",
            gr.update(),
        )


def _open_source(evt: gr.SelectData, retrieved_state) -> str:
    row = evt.index[0]
    if row < len(retrieved_state):
        return _open_file(retrieved_state[row].source)
    return "未找到源文件"


# ================= 文档库 =================
def _doc_rows(tag_filter=None) -> list:
    docs = pipe.documents()
    if tag_filter:
        docs = [d for d in docs if tag_filter in (d.get("tags") or [])]
    return [
        [
            d["name"],
            d["chunks"],
            Path(d["source"]).name,
            d.get("tenant", "default"),
            d.get("lifecycle", "active"),
            ",".join(d.get("tags", [])),
            _fmt_time(d["indexed_at"]),
        ]
        for d in docs
    ]


def _doc_table(tag_filter=None) -> gr.update:
    return gr.update(value=_doc_rows(tag_filter))


def _tags_choices() -> gr.update:
    return gr.update(choices=pipe.all_tags())


def _doc_detail(selected_doc) -> str:
    if not selected_doc:
        return "（未选中文档）"
    for d in pipe.documents():
        if d["name"] == selected_doc:
            tags = "、".join(d.get("tags", [])) or "（无）"
            return (
                f"**{d['name']}**  \n"
                f"- 源文件：`{d.get('source')}`  \n"
                f"- 块数：{d['chunks']}  \n"
                f"- 租户：{d.get('tenant', 'default')} ｜ 生命周期：{d.get('lifecycle', 'active')}  \n"
                f"- 标签：{tags}  \n"
                f"- 索引时间：{_fmt_time(d['indexed_at'])}"
            )
    return "（文档不存在）"


def _upload(files, tenant, lifecycle, tags_text) -> tuple:
    if not files:
        return "请先选择文件。", gr.update(), _tags_choices(), _tags_choices()
    tags = [t.strip() for t in (tags_text or "").split(",") if t.strip()]
    msgs = []
    for f in files:
        name = Path(f).name
        dest = UPLOAD_DIR / name
        if dest.exists():
            dest = UPLOAD_DIR / f"{Path(f).stem}_{int(time.time())}{Path(f).suffix}"
        try:
            shutil.copy(f, dest)
            r = pipe.index(
                str(dest), tenant=tenant or None, lifecycle=lifecycle or None, tags=tags
            )
            msgs.append(
                f"✅《{r['doc']}》：{r['chunks']} 块（{r['mode']}，"
                f"租户 {tenant or 'default'} / {lifecycle or 'active'}，"
                f"标签 {r.get('tags', [])}）"
            )
        except Exception as e:  # noqa: BLE001
            msgs.append(f"❌ {name}：{e}")
    return "\n".join(msgs), _doc_table(), _tags_choices(), _tags_choices()


def _select_doc(evt: gr.SelectData, tag_filter) -> tuple:
    row = evt.index[0]
    docs = pipe.documents()
    if tag_filter:
        docs = [d for d in docs if tag_filter in (d.get("tags") or [])]
    name = docs[row]["name"] if row < len(docs) else None
    return name, _doc_detail(name)


def _set_doc_tags(selected_doc, tags_text) -> tuple:
    if not selected_doc:
        return "请先在表格中选中文档。", gr.update(), gr.update(), gr.update()
    tags = [t.strip() for t in (tags_text or "").split(",") if t.strip()]
    pipe.set_doc_tags(selected_doc, tags)
    return (
        f"已更新《{selected_doc}》标签：{tags}",
        _doc_table(),
        _tags_choices(),
        _tags_choices(),
    )


def _add_doc_tags(selected_doc, tags_text) -> tuple:
    if not selected_doc:
        return "请先选中文档。", gr.update(), gr.update(), gr.update()
    tags = [t.strip() for t in (tags_text or "").split(",") if t.strip()]
    for t in tags:
        pipe.add_doc_tag(selected_doc, t)
    return f"已添加标签：{tags}", _doc_table(), _tags_choices(), _tags_choices()


def _remove_doc_tags(selected_doc, tags_text) -> tuple:
    if not selected_doc:
        return "请先选中文档。", gr.update(), gr.update(), gr.update()
    tags = [t.strip() for t in (tags_text or "").split(",") if t.strip()]
    for t in tags:
        pipe.remove_doc_tag(selected_doc, t)
    return f"已删除标签：{tags}", _doc_table(), _tags_choices(), _tags_choices()


def _set_doc_lifecycle(selected_doc, lifecycle) -> tuple:
    if not selected_doc:
        return "请先选中文档。", gr.update(), gr.update()
    pipe.set_doc_lifecycle(selected_doc, lifecycle)
    return (
        f"已更新《{selected_doc}》生命周期 → {lifecycle}",
        _doc_table(),
        _doc_detail(selected_doc),
    )


def _reindex_doc(selected_doc) -> tuple:
    if not selected_doc:
        return "请先选中文档。", gr.update()
    try:
        r = pipe.reindex(selected_doc)
        return f"已重新索引《{selected_doc}》：{r['chunks']} 块（{r['mode']}）", _doc_table()
    except Exception as e:  # noqa: BLE001
        return f"❌ 重新索引失败：{e}", gr.update()


def _auto_tag_doc(selected_doc) -> tuple:
    if not selected_doc:
        return "请先选中文档。", gr.update(), gr.update(), gr.update()
    try:
        tags = pipe.auto_tag(selected_doc)
        return f"《{selected_doc}》自动标签：{tags}", _doc_table(), _tags_choices(), _tags_choices()
    except Exception as e:  # noqa: BLE001
        return f"❌ {e}", gr.update(), gr.update(), gr.update()


def _auto_tag_all() -> tuple:
    msgs = []
    for d in pipe.documents():
        try:
            tags = pipe.auto_tag(d["name"])
            msgs.append(f"《{d['name']}》→ {tags}")
        except Exception as e:  # noqa: BLE001
            msgs.append(f"❌ {d['name']}: {e}")
    return "\n".join(msgs), _doc_table(), _tags_choices(), _tags_choices()


def _refresh_lib() -> tuple:
    return _doc_table(), _tags_choices(), _tags_choices()


def _delete_doc(selected_doc) -> tuple:
    if not selected_doc:
        return "请先在表格中选中要删除的文档。", gr.update(), gr.update(), gr.update()
    pipe.delete_doc(selected_doc)
    return f"已删除《{selected_doc}》", _doc_table(), _tags_choices(), _tags_choices()


def _search_lib(q) -> tuple:
    if not q.strip():
        return gr.update(value=[]), []
    rs = pipe.retriever.retrieve(q, top_k=6, use_rerank=False, route_hint=q)
    rows = [
        [f"[{r.index}]", r.doc_name, r.section, r.text.replace("\n", " ")[:60]]
        for r in rs
    ]
    return gr.update(value=rows), rs


def _open_search(evt: gr.SelectData, search_retrieved) -> str:
    row = evt.index[0]
    if row < len(search_retrieved):
        return _open_file(search_retrieved[row].source)
    return "未找到源文件"


# ================= UI（完全参考 GPT-Gradio-Agent） =================
def build_ui() -> gr.Blocks:
    init_sessions = pipe.sessions.list_sessions()
    init_sid = init_sessions[0]["id"] if init_sessions else None
    init_history = (
        [{"role": m["role"], "content": m["content"]} for m in pipe.sessions.all(init_sid)]
        if init_sid else []
    )

    with gr.Blocks(title="MemoDoc — 带长期记忆的文档问答", css="style/style.css") as demo:
        gr.Markdown(
            """
            # <center>📚 MemoDoc</center>
            <center>带长期记忆的文档问答 Agent —— 上传文档 → 提问 → 引用溯源 → 跨会话记忆</center>
            """
        )

        with gr.Row(elem_classes="col-container"):
            # ===== 左侧：会话栏（#history） =====
            with gr.Column(elem_id="history"):
                with gr.Row():
                    new_btn = gr.Button(
                        value="新对话",
                        icon="icon/add_dialog.png",
                        elem_id="btn_transparent",
                        size="sm",
                    )
                    del_btn = gr.Button(
                        value="删除会话",
                        icon="icon/delete_dialog.png",
                        elem_id="btn_transparent",
                        size="sm",
                    )
                session_radio = gr.Radio(
                    choices=[s["title"] for s in init_sessions],
                    value=init_sessions[0]["title"] if init_sessions else None,
                    show_label=False,
                    interactive=True,
                    elem_id="history-select-dropdown",
                )

            # ===== 中间：对话主区（scale=4，CSS 网格占 2.5fr） =====
            with gr.Column(scale=4):
                with gr.Tabs():
                    # ---------- 对话 ----------
                    with gr.Tab("对话"):
                        chatbot = gr.Chatbot(
                            type="messages",
                            height=560,
                            show_label=False,
                            show_copy_button=True,
                            allow_tags=False,
                        )
                        with gr.Row():
                            message = gr.Textbox(
                                label="输入你的问题",
                                scale=7,
                                placeholder="例如：入社需要满足哪些条件？",
                            )
                            send = gr.Button("发送", variant="primary", scale=1, elem_id="btn")
                        with gr.Row():
                            use_memory = gr.Checkbox(value=True, label="🧠 使用长期记忆", scale=2)
                            clear_chat = gr.Button("清空对话（保留记忆）", size="sm")
                            clear_mem = gr.Button("清空记忆", size="sm")
                        scope_tags = gr.Dropdown(
                            label="🔍 检索范围：按标签过滤（多选，空 = 全部文档）",
                            choices=pipe.all_tags(), multiselect=True,
                        )
                        status = gr.Markdown("")

                    # ---------- 文档库 ----------
                    with gr.Tab("文档库"):
                        with gr.Row():
                            upload_files = gr.File(
                                label="批量上传文档（PDF / MD / TXT）",
                                file_count="multiple", type="filepath", scale=4,
                            )
                            upload_btn = gr.Button("上传并索引", variant="primary", scale=1, elem_id="btn")
                        with gr.Row():
                            tenant_box = gr.Textbox(label="租户", value="default", scale=1)
                            lifecycle_box = gr.Dropdown(
                                label="生命周期", choices=["active", "archive", "draft"],
                                value="active", scale=1,
                            )
                            tags_box = gr.Textbox(
                                label="虚拟标签（逗号分隔）", scale=2,
                                placeholder="例如：论文, 记忆系统",
                            )
                        lib_status = gr.Markdown("")
                        with gr.Row():
                            gr.Markdown("### 📚 文档库（点击行选中，可删除）")
                            refresh_btn = gr.Button("刷新", size="sm")
                            del_doc_btn = gr.Button("删除选中", size="sm")
                        with gr.Row():
                            lib_tag_filter = gr.Dropdown(
                                label="按标签筛选（空 = 全部，像打开文件夹）",
                                choices=pipe.all_tags(), scale=3,
                            )
                            tag_edit_box = gr.Textbox(
                                label="设置选中文档标签（逗号分隔）", scale=3,
                                placeholder="例如：论文, 记忆系统, 已归档",
                            )
                            tag_set_btn = gr.Button("设置标签", scale=1, elem_id="btn")
                        with gr.Row():
                            tag_add_box = gr.Textbox(
                                label="添加标签（逗号分隔）", scale=2,
                                placeholder="例如：论文, 重要",
                            )
                            tag_add_btn = gr.Button("添加", scale=1, elem_id="btn")
                            tag_del_box = gr.Textbox(
                                label="删除标签（逗号分隔）", scale=2,
                                placeholder="例如：已归档",
                            )
                            tag_del_btn = gr.Button("删除", scale=1, elem_id="btn")
                        with gr.Row():
                            lifecycle_edit = gr.Dropdown(
                                label="修改选中文档生命周期", choices=["active", "archive", "draft"],
                                value="active", scale=2,
                            )
                            lifecycle_set_btn = gr.Button("改生命周期", scale=1, elem_id="btn")
                            reindex_btn = gr.Button("重新索引", scale=1, elem_id="btn")
                        with gr.Row():
                            auto_tag_btn = gr.Button("🤖 自动打标签（选中）", scale=1, elem_id="btn")
                            auto_tag_all_btn = gr.Button("🤖 全部自动打标签", scale=1, elem_id="btn")
                        doc_detail = gr.Markdown("（未选中文档）")
                        doc_table = gr.Dataframe(
                            value=_doc_rows(),
                            headers=["文档名", "块数", "来源", "租户", "生命周期", "标签", "索引时间"],
                            interactive=False, wrap=True,
                        )
                        with gr.Row():
                            search_box = gr.Textbox(
                                label="库内检索", scale=4,
                                placeholder="在所有文档中搜索…（例如：报销 200 元）",
                            )
                            search_btn = gr.Button("检索", scale=1, elem_id="btn")
                        search_status = gr.Markdown("")
                        gr.Markdown("### 🔎 检索结果（点击行打开源文件）")
                        search_results = gr.Dataframe(
                            headers=["编号", "文档", "章节", "片段预览"],
                            interactive=False, wrap=True,
                        )

            # ===== 右侧：引用来源 + 长期记忆（参考其右侧设置面板风格） =====
            with gr.Column():
                with gr.Tabs():
                    with gr.Tab("引用来源"):
                        with gr.Accordion("引用来源（点击行打开源文件）", elem_id="Accordion", open=True):
                            sources_df = gr.Dataframe(
                                headers=["编号", "文档", "章节", "片段预览", "核查"],
                                interactive=False, wrap=True,
                            )
                    with gr.Tab("长期记忆"):
                        with gr.Accordion("长期记忆（跨会话记住你）", elem_id="Accordion", open=True):
                            memories = gr.HTML(render_memories(pipe.list_memories()))

        # ---------- 状态 ----------
        current_session = gr.State(init_sid)
        retrieved_state = gr.State([])
        search_retrieved = gr.State([])
        selected_doc = gr.State(None)

        # ---------- 事件 ----------
        new_btn.click(
            _new_session, None,
            [current_session, chatbot, session_radio, status],
        )
        session_radio.select(
            _switch_session, None,
            [current_session, chatbot, sources_df, memories, status],
        )
        del_btn.click(
            _delete_session, [current_session],
            [current_session, chatbot, session_radio, status],
        )

        send.click(
            respond,
            [message, chatbot, use_memory, current_session, scope_tags],
            [chatbot, sources_df, memories, message, session_radio, current_session, status, retrieved_state],
        )
        message.submit(
            respond,
            [message, chatbot, use_memory, current_session, scope_tags],
            [chatbot, sources_df, memories, message, session_radio, current_session, status, retrieved_state],
        )
        sources_df.select(_open_source, [retrieved_state], [status])
        clear_chat.click(_clear_chat, [current_session], [chatbot, session_radio, status])
        clear_mem.click(_clear_mem, None, [memories, status])

        upload_btn.click(
            _upload, [upload_files, tenant_box, lifecycle_box, tags_box],
            [lib_status, doc_table, scope_tags, lib_tag_filter],
        )
        refresh_btn.click(_refresh_lib, None, [doc_table, scope_tags, lib_tag_filter])
        doc_table.select(_select_doc, [lib_tag_filter], [selected_doc, doc_detail])
        lib_tag_filter.change(_doc_table, [lib_tag_filter], [doc_table])
        tag_set_btn.click(
            _set_doc_tags, [selected_doc, tag_edit_box],
            [lib_status, doc_table, scope_tags, lib_tag_filter],
        )
        tag_add_btn.click(
            _add_doc_tags, [selected_doc, tag_add_box],
            [lib_status, doc_table, scope_tags, lib_tag_filter],
        )
        tag_del_btn.click(
            _remove_doc_tags, [selected_doc, tag_del_box],
            [lib_status, doc_table, scope_tags, lib_tag_filter],
        )
        lifecycle_set_btn.click(
            _set_doc_lifecycle, [selected_doc, lifecycle_edit],
            [lib_status, doc_table, doc_detail],
        )
        reindex_btn.click(_reindex_doc, [selected_doc], [lib_status, doc_table])
        auto_tag_btn.click(
            _auto_tag_doc, [selected_doc], [lib_status, doc_table, scope_tags, lib_tag_filter]
        )
        auto_tag_all_btn.click(
            _auto_tag_all, None, [lib_status, doc_table, scope_tags, lib_tag_filter]
        )
        del_doc_btn.click(
            _delete_doc, [selected_doc], [lib_status, doc_table, scope_tags, lib_tag_filter]
        )
        search_btn.click(_search_lib, [search_box], [search_results, search_retrieved])
        search_results.select(_open_search, [search_retrieved], [search_status])

    demo.theme = _adjust_theme()
    return demo


if __name__ == "__main__":
    build_ui().queue().launch()
