# MemoDoc — 带长期记忆的文档问答 Agent（学习助手）

> 小学期实践项目（软件开发方向）。核心思路借鉴 **Kotaemon（RAG）** 与 **mem0（长期记忆）** 两个开源范式，
> 自研三条数据流（索引 / 问答 / 记忆），并包装为面向教育场景的**长线学习助手**：教师上传课件/作业/往年题形成班级知识库，
> 学生在复习问答中被记住薄弱点，教师据此优化教学。数据不出校、引用可追溯、记忆长线积累。

上传一份文档，然后像聊天一样提问：它**流式回答**、用 `[1][2]` **引用原文**，点击引用来源可直接打开源文件；
更重要的是，它会**记住你**——这次说"我是大一新生，状态图画不好"，下次新会话它会带着这个记忆回答。

## 分支说明

| 分支 | 内容 |
| --- | --- |
| **main** | 小学期**最终展示版**：前端 React + TypeScript 全面重写，后端 FastAPI 包装（`src/` 的 RAG/Memory 核心逻辑冻结未动） |
| **master** | **复现版**：完整保留 Gradio 版实现与全部中间产物，供后续项目复现 |

## 特性

- **三条数据流**：索引流（文档 → 分块 → embedding → 向量库）、问答流（检索 + 记忆 + 历史 → 流式生成 + 引用）、记忆流（LLM 抽取事实 → 去重/冲突更新 → 新会话注入）。
- **RAG**：PyMuPDF 解析 PDF/MD/TXT；标题感知分块；本地 `bge-small-zh-v1.5` embedding；**混合检索（手写 BM25 + 向量加权融合，对齐 Kotaemon 设计）** + **交叉编码器重排（bge-reranker-v2-m3）**；自研轻量向量库（numpy 余弦 + JSON 持久化）；**引用核查**（LLM 逐条验证 `[n]` 是否真的被片段支持）。
- **跨语言检索**：中文查询自动翻译成英文、双语融合检索——用中文问英文论文也能命中并作答。
- **文档路由**：查询提及文档标题时，自动限定到该文档域内检索（解决"xx论文的摘要/贡献"这类问题的串文档干扰）。
- **逻辑空间**：物理层按「租户/生命周期」归档文件（`data/uploads/<租户>/<生命周期>/`）；逻辑层向量库保持扁平，用 `tenant/lifecycle/tags` **虚拟标签**管理；**支持自动打标签**（LLM 建议 + 启发式兜底，索引时自动触发，也可一键重打）；问答区可**勾选标签限定检索区间**，文档库可**按标签筛选/编辑**（像文件夹一样管理文件库）。
- **长期记忆（mem0 范式）**：LLM 抽取「身份 / 偏好」结构化事实，向量去重 + 同属性冲突更新，新会话自动注入相关记忆。
- **记忆增强检索**：bge 中文查询指令前缀 + 把相关记忆拼进查询再检索——"我是大一新生，还需要交会费吗"这类问题能精准命中「入社条件」块，实现个性化回答与精确引用双赢。
- **学习助手（产品层，main 分支）**：**双角色**（学生复习问答 / 教师课件问答+资料库+班级统计）、**文档分类**（课程 × 类型：课件/作业题/往年题/错题）、**学习画像**（问答中抽取薄弱知识点，右栏实时展示）、**班级薄弱点聚合统计**（教师端）、学生身份可切换（张三/李四/王五，演示多人生成统计）。
- **演示友好（React 前端）**：React 18 + TypeScript + Ant Design + Zustand；头部角色切换、左侧会话栏、中间主区、右栏「引用来源 + 学习画像」；`[n]` 引用 chip 点击直接打开源文件；引用核查徽标（✓已核查 / ⚠不支持）；SSE 流式逐字渲染。
- **可评测**：`tests/eval.py` 输出检索召回率（纯向量/混合/混合+重排三档）、引用准确率、关键词覆盖、引用核查通过率；**支持按标签限定评测范围**（`--tags 演示` / `--tags 论文`）；`tests/eval_papers.py` 面向**英文论文的跨语言评测**（中文提问 × 关键词黄金标准 × 文档路由，11 条用例覆盖 8 篇论文）；`tests/eval_ragas.py` 跑 RAGAS 四指标（faithfulness/相关性/上下文精度与召回）。

## 快速开始（main 分支）

```bash
# 1. 建 Python 环境并安装后端依赖
uv sync

# 2. 配置密钥
copy .env.example .env      # 然后编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 构建前端（首次需要 npm）
cd frontend
npm install
npm run build
cd ..

# 4. 启动（FastAPI 同时托管 React 构建产物）
.venv\Scripts\python.exe server.py
```

浏览器打开 `http://127.0.0.1:8000`。开发模式可另开终端 `cd frontend && npm run dev`（5173 端口，`/api` 自动代理到 8000）。

一键启动（构建完成后）：双击 `start.bat`。

> 复现版（master 分支）：`uv run python app.py` 启动 Gradio 版，见该分支 README。

命令行工具（后端能力，两分支通用）：

```bash
uv run memodoc index data/demo_doc.md
uv run memodoc ask "入社需要满足哪些条件？"
uv run memodoc docs
uv run memodoc memories
uv run memodoc download-model   # 模型缺失时重新下载到 data/models
```

评测：

```bash
uv run python tests/eval.py
uv run python tests/eval_papers.py
uv run python tests/eval_ragas.py
```

## 项目结构（main 分支）

```
memodoc/
├── server.py                 # 入口：uvicorn 启动 FastAPI（托管 React 构建产物）
├── api/
│   ├── server.py             # FastAPI：会话/SSE 流式问答/上传/文档库/画像/统计/打开源文件
│   └── services.py           # 产品层：文档分类元数据 + 学习画像抽取 + 班级统计
├── frontend/                 # React 18 + TypeScript + Vite 前端（见 frontend/README.md）
│   ├── vite.config.ts / tsconfig*.json / package.json
│   └── src/                  # types / api / store / App / 7 个组件 / styles.css
├── src/memodoc/              # 核心（两分支共用，RAG/Memory 逻辑冻结）
│   ├── config.py             # pydantic-settings 配置
│   ├── llm/openai_compat.py  # DeepSeek/Kimi 统一客户端（chat/stream/json）
│   ├── rag/                  # parser / chunker / embedder / store / sparse / reranker / retriever / generator
│   ├── memory/               # extractor / store / injector
│   ├── session.py            # 会话历史 jsonl
│   ├── tagger.py             # 自动打标签（LLM 建议 + 启发式兜底）
│   ├── pipeline.py           # 三条链路编排 + 引用核查
│   ├── model.py              # 模型断点续传下载
│   └── cli.py                # 命令行入口
├── app.py                    # 【复现版】Gradio UI（master 分支入口，main 分支保留备用）
├── data/demo_doc.md          # 受控演示文档
├── start.bat                 # 一键启动
└── tests/                    # eval.py / eval_papers.py / eval_ragas.py / smoke.py
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
5. **前端两分支策略**：master 用 Gradio（轻量复现）；main 用 **React + FastAPI**（展示版）——产品 UI 复杂度（双角色/仪表盘/图表）超过 Gradio 状态管理天花板，React 是正确的长期工具；`src/` 核心两分支共用且冻结。
6. **向量库自研而非 ChromaDB**：本机无 MSVC 构建工具，ChromaDB 的 chroma-hnswlib 无 Windows/3.12 预编译 wheel；演示规模下 O(n) 精确检索毫秒级完成，JSON 存储可审计、零原生依赖，且接口对齐 ChromaDB、后续可无缝替换。
7. **产品层与核心解耦**：文档分类元数据、学习画像、班级统计全部放在 `api/services.py`（新增模块），组合核心的公开接口，不修改 `src/`——保证复现版与展示版共享同一核心。

详见 `docs/ARCHITECTURE.md`、`docs/DESIGN_SPEC.md` 与 `docs/PRODUCT_PLAN.md`。
