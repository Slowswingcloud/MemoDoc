# MemoDoc — 带长期记忆的文档问答 Agent

> 小学期实践项目。核心思路借鉴 **Kotaemon（RAG）** 与 **mem0（长期记忆）** 两个开源范式，
> 用自研的三条数据流把它们拼成一个可答辩、可演示、可评测的最小系统。

上传一份文档，然后像聊天一样提问：它**流式回答**、用 `[1][2]` **引用原文**并在右侧**高亮来源**；
更重要的是，它会**记住你**——这次说"我是大一新生"，下次新会话它会带着这个记忆回答。

## 特性

- **三条数据流**：索引流（文档 → 分块 → embedding → 向量库）、问答流（检索 + 记忆 + 历史 → 流式生成 + 引用）、记忆流（LLM 抽取事实 → 去重/冲突更新 → 新会话注入）。
- **RAG**：PyMuPDF 解析 PDF/MD/TXT；标题感知分块；本地 `bge-small-zh-v1.5` embedding（离线、免费）；自研轻量向量库（numpy 余弦 + JSON 持久化，接口对齐 ChromaDB）；Top-K 检索（embedding 不可用时自动回退关键词检索）。
- **长期记忆（mem0 范式）**：LLM 抽取「身份 / 偏好」两类结构化事实，向量去重 + 同属性冲突更新，新会话自动注入相关记忆。
- **演示友好**：流式打字、`[n]` 引用点击高亮源片段、记忆面板实时刷新、**「使用长期记忆」开关**（一键对比有记忆 vs 无记忆）。
- **可评测**：`tests/eval.py` 输出检索召回率、引用准确率、关键词覆盖三个真实数字。

## 快速开始

```bash
# 1. 建环境并安装（自动创建 .venv，Python 3.11/3.12）
uv sync

# 2. 配置密钥
copy .env.example .env      # 然后编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 索引演示文档（首次会下载 bge 模型约 100MB，默认从 huggingface.co 下载；有代理时走系统代理）
uv run memodoc index data/demo_doc.md

# 4. 启动 Web UI
uv run python app.py
```

浏览器打开 `http://127.0.0.1:7860`。

命令行提问：

```bash
uv run memodoc ask "入社需要满足哪些条件？"
uv run memodoc docs
uv run memodoc memories
```

评测：

```bash
uv run python tests/eval.py
```

## 项目结构

```
memodoc/
├── app.py                    # Gradio UI（流式/引用高亮/记忆面板/有无记忆开关）
├── data/demo_doc.md          # 受控演示文档
├── src/memodoc/
│   ├── config.py             # pydantic-settings 配置
│   ├── llm/openai_compat.py  # DeepSeek/Kimi 统一客户端（chat/stream/json）
│   ├── rag/                  # parser / chunker / embedder / store / retriever / generator
│   ├── memory/               # extractor / store / injector
│   ├── session.py            # 会话历史 jsonl
│   ├── pipeline.py           # 三条链路编排
│   └── cli.py                # 命令行入口
└── tests/eval.py             # 效果评测
```

## 配置项（.env）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | — | 必填 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | 换 Kimi 填 `https://api.moonshot.cn/v1` |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 主用 V3（流式快、引用干脆） |
| `EMBED_DEVICE` | `cpu` | 本机有 RTX 4060 可改 `cuda` |
| `HF_ENDPOINT` | `https://huggingface.co` | 模型下载源，可用 `.env` 的 `hf_endpoint` 或环境变量覆盖 |

> **模型下载与代理**：默认从 `huggingface.co` 下载 bge 模型，会遵循系统代理
> （`HTTP_PROXY` / `HTTPS_PROXY` 环境变量）。如果你的网络直连被墙，
> 请确保代理已开启且环境变量已设置（本机为 `http://127.0.0.1:7897`）。
> 若无代理，可在 `.env` 中把 `hf_endpoint` 改成你可达的镜像站。

## 设计决策（ADR）

1. **本地 embedding 而非 API**：DeepSeek/Kimi 均无 embedding 端点；本地化同时解决免费与离线演示。
2. **RAG 与 Memory 分两层**：单一职责，换记忆方案不动检索、换检索方案不动记忆。
3. **记忆存「结构化事实」而非原文**：mem0 验证过的范式，支持跨会话结构化更新与去重。
4. **生成强制「只依据检索片段 + 引用编号」**：压制幻觉，引用是答辩的可视化证据。
5. **UI 用 Gradio 而非 React**：时间约束下的工程取舍，React 版是后续演进方向。
6. **向量库自研而非 ChromaDB**：本机无 MSVC 构建工具，ChromaDB 的 chroma-hnswlib 无 Windows/3.12 预编译 wheel；演示规模下 O(n) 精确检索毫秒级完成，JSON 存储可审计、零原生依赖，且接口对齐 ChromaDB、后续可无缝替换。

详见 `docs/ARCHITECTURE.md` 与 `docs/DEMO.md`。
