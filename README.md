# MemoDoc —— 带长期记忆的文档问答 Agent（学习助手）

> 把课程资料变成**一位记得住你的问答助教**：上传课件/作业/往年题，像聊天一样提问，回答**流式输出**、带 `[1][2]` **原文引用**（点击直接打开源文件、逐条核查打标）；更重要的是它会**跨会话记住你**——这次说"我是大一新生，状态图画不好"，下次新会话它带着这个记忆回答。

- 后端：Python 3.12 + **FastAPI**（Web 层）＋ 自研核心（手写 **BM25** + 本地向量库 + **bge** 中文 embedding/重排）
- 前端：React 18 + TypeScript + Vite + Ant Design + Zustand
- 大模型：DeepSeek（OpenAI 兼容，外接 API）；数据与模型均本地化，**可离线演示**

---

## 它能做什么（核心特性）

| 能力 | 说明 |
| --- | --- |
| 📄 文档问答 | 上传 PDF / Markdown / TXT → 自动解析、标题感知分块、向量化 + BM25 建索引 → 针对文件库提问 |
| 🔗 引用可溯源 | 回答强制 `[n]` 编号引用；点 `[n]` 用系统默认程序**打开源文件**；来源面板同步展示片段 |
| ✅ 引用核查 | 每条引用由 LLM 逐条判定「✓已核查 / ⚠不支持」，抗幻觉、可交代 |
| 🧠 长期记忆 | 每轮问答后自动抽取你的**身份/偏好**事实，去重与冲突更新入库；新会话自动注入相关记忆（mem0 范式） |
| 🏷 标签管理 | 文档自动/手动打标签；问答前可按标签**限定检索区间**（像文件夹一样管理文件库） |
| 👥 多用户 | 注册/登录，会话按用户隔离；上传者或管理员可删文档；管理员可看全部用户 |
| 💬 SSE 流式 | 检索来源先到、正文逐字渲染，等待感低 |
| 🌐 跨语言检索 | 中文提问可命中英文论文（自动翻译 + 双语融合检索 + 多语言重排） |

---

## 快速开始（Windows）

### 1. 准备环境

- Python 3.11–3.12（推荐 3.12）
- [uv](https://docs.astral.sh/uv/)（可选；不用 uv 就用 `python -m venv` + `pip`）
- Node.js 18+（仅构建前端需要一次）

### 2. 安装依赖

```powershell
# 在项目根目录
uv sync                     # 可选替代：python -m venv .venv && .venv\Scripts\pip install -e .
```

### 3. 配置密钥

```powershell
copy .env.example .env      # 然后编辑 .env，填入 DEEPSEEK_API_KEY=sk-...
```

### 4. 下载本地模型（可断点续传；若 `data/models/` 已随包提供可跳过）

```powershell
.venv\Scripts\python.exe -m memodoc.cli download-model
.venv\Scripts\python.exe -m memodoc.cli download-model --rerank
```

### 5. 构建前端（首次）

```powershell
cd frontend
npm install
npm run build
cd ..
```

### 6. 启动

```powershell
.venv\Scripts\python.exe server.py
```

浏览器打开 **http://127.0.0.1:8000** —— 首次启动若账号库为空会自动创建默认管理员 **`admin` / `admin123`**。

> 已构建过一次后，日常直接双击根目录 **`start.bat`** 一键启动。
> 开发模式（前端热更新）：后端 `python server.py` 跑在 8000，另开终端 `cd frontend && npm run dev`，访问 http://127.0.0.1:5173（`/api` 自动代理到 8000）。

---

## 怎么用（使用指南）

1. **登录/注册**：`admin/admin123` 登录，或注册普通账号（user 角色）。
2. **建知识库**：进入「📚 文件库」→ 选择文件（PDF/MD/TXT，可多选）→ 可选填标签 → 上传。系统自动索引；未填标签会自动打标签。列表里可加/删标签、下载、删除（仅上传者或管理员）。
3. **提问**：切到「💬 问答」，输入问题或点建议问题（如"状态图怎么画？"）。回答逐字流式出现，右栏同步展示引用来源。
4. **溯源**：回答里的 `[n]` 是可点击 chip → 点击即打开源文件；来源卡片显示「✓已核查 / ⚠不支持」徽标。
5. **限定检索区间**：问答框上方可多选标签，提问只在带这些标签的文档里检索。
6. **会话**：左侧栏新建/切换/删除会话，历史自动保存、按用户隔离。
7. **记忆（自动）**：不用手动开——回答完自动抽取你的身份/偏好记忆，新会话自动生效。命令行查看/清空：
   ```powershell
   .venv\Scripts\python.exe -m memodoc.cli memories
   ```
8. **管理员**：「👥 用户管理」查看全部账号。

---

## 命令行工具（后端能力，无需打开网页）

```powershell
.venv\Scripts\python.exe -m memodoc.cli index data/demo_doc.md      # 索引一份文档
.venv\Scripts\python.exe -m memodoc.cli ask "入社需要满足哪些条件？"  # 提问
.venv\Scripts\python.exe -m memodoc.cli docs                        # 已索引文档
.venv\Scripts\python.exe -m memodoc.cli memories                    # 长期记忆
.venv\Scripts\python.exe -m memodoc.cli download-model              # 模型下载
```

---

## 测试与评测

```powershell
# 接口冒烟/用例（进程内 TestClient）：当前 28/28 通过（见 docs/TEST_REPORT.md）
.venv\Scripts\python.exe tests\smoke.py
# 检索/引用指标：纯向量 vs BM25 vs 融合 三档召回、引用准确率、核查通过率
.venv\Scripts\python.exe tests\eval.py
# 英文论文跨语言评测 / RAGAS 端到端指标（可选，见 docs/BENCHMARK.md）
.venv\Scripts\python.exe tests\eval_papers.py
.venv\Scripts\python.exe tests\eval_ragas.py
```

---

## 项目结构

```
├── server.py                 # 启动入口：uvicorn 拉起 FastAPI（托管前端构建产物）
├── start.bat                 # Windows 一键启动
├── pyproject.toml / uv.lock  # 后端依赖（uv）
├── .env.example              # 配置模板
├── api/                      # FastAPI Web 层
│   ├── server.py             # 路由：认证/会话/SSE 问答/文档库/标签/上传/下载/打开源文件
│   ├── auth.py               # 账号（user/admin、加盐哈希、令牌）
│   └── services.py           # 文档所有权元数据
├── src/memodoc/              # 核心（RAG + Memory）
│   ├── config.py             # pydantic-settings 配置
│   ├── llm/openai_compat.py  # DeepSeek/Kimi 统一客户端
│   ├── rag/                  # parser / chunker / embedder / store(向量库) / sparse(BM25)
│   │                         #  / reranker / retriever(融合+路由) / generator
│   ├── memory/               # extractor / store(去重冲突) / injector
│   ├── session.py            # 会话 jsonl；tagger.py 自动打标签
│   ├── pipeline.py           # 索引/问答/记忆 三条链路 + 引用核查
│   ├── model.py              # 模型断点续传下载；cli.py 命令行
├── frontend/                 # React 18 + TS 前端（npm run build 后由后端托管）
│   └── src/                  # types / api / store / App / components(7) / styles.css
├── tests/                    # smoke / test_project(接口用例) / eval*（评测脚本）
├── docs/                     # ARCHITECTURE.md / DESIGN_SPEC.md / TEST_REPORT.md / BENCHMARK.md
├── 软件开发文档.md             # 课程开发文档（提交前重命名：学号+姓名+作品名称）
└── data/                     # 运行时数据（uploads 源文件 / store 索引与账号 / sessions / models）
```

---

## 配置项（.env）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | — | 必填 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | 换 Kimi 填 `https://api.moonshot.cn/v1` |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 主用模型 |
| `EMBED_DEVICE` | `cpu` | 有 CUDA 显卡可改 `cuda` |
| `HF_ENDPOINT` | `https://huggingface.co` | 模型下载源；无代理可改镜像如 `https://hf-mirror.com` |

---

## 常见问题

- **没有 API Key 能跑吗？** 能。问答生成会提示未配置 key；检索/索引链路不依赖云端 key。建议先 `download-model` 让本地模型就位。
- **模型下载慢/失败？** 支持断点续传，重跑命令即可续；网络受限请在 `.env` 把 `HF_ENDPOINT` 换成可达镜像。
- **怎么用 GPU 加速检索/索引？** 默认 torch 是 CPU 版；本机有 NVIDIA 显卡（驱动需支持 CUDA 12.x）时执行一次：
  ```powershell
  uv pip install --python .venv\Scripts\python.exe --index-url https://download.pytorch.org/whl/cu128 "torch==2.9.1+cu128"
  ```
  然后把 `.env` 的 `EMBED_DEVICE` 改为 `cuda` 并重启。实测（RTX 4060）：embedding 约 5ms/块、重排约 51ms/对，比 CPU 快 20–40 倍。注意：之后若再执行 `uv sync` 会按锁文件把 torch 还原为 CPU 版，需重装上述命令。
- **想重置演示数据？** 删除 `data/store/users.json`、`data/store/tokens.json` 与 `data/sessions/` 下文件后重启，会自动重建默认管理员。
- **8080/8000 端口被占？** 修改 `server.py` 中的 `port`。

详细设计见 `docs/ARCHITECTURE.md`（架构与关键实现细节）、`docs/DESIGN_SPEC.md`、`docs/TEST_REPORT.md`（28/28 接口测试）、`docs/BENCHMARK.md`（评测接入指南），课程文档见根目录「软件开发文档.md」。
