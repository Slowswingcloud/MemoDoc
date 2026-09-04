# MemoDoc 前端（React + TypeScript）

> MemoDoc 文档问答系统的展示端：React 18 + TypeScript 5 + Vite 5 + Ant Design 5 + Zustand 4。
> 消费后端 `api/server.py`（FastAPI）的 REST + SSE 接口；后端核心 RAG/Memory 逻辑在 `src/memodoc/`。

## 运行

```bash
# 1) 安装依赖（首次）
npm install

# 2a) 开发模式（后端需运行在 8000：项目根执行 python server.py）
npm run dev          # http://127.0.0.1:5173（/api 自动代理到 8000）

# 2b) 生产模式（构建后由 FastAPI 托管）
npm run build        # 产物在 dist/，项目根 python server.py 后访问 http://127.0.0.1:8000
```

## src 结构

```
src/
├── main.tsx / App.tsx     # 挂载；三栏布局（会话栏 / 问答·文件库·用户管理 / 引用面板）
├── types.ts               # 共享类型（用户/会话/消息/引用/核查/文档/SSE 事件）
├── api.ts                 # fetch 封装 + SSE 流式客户端（chatStream）
├── store.ts               # Zustand 全局状态与动作（登录/会话/发送/文档/标签）
├── styles.css             # 全局样式
└── components/
    ├── AuthPage.tsx       # 登录/注册（注册可选 user/admin 角色）
    ├── Sidebar.tsx        # 会话列表（新建/切换/删除）
    ├── ChatPanel.tsx      # 问答主区：建议问题、标签过滤、消息流
    ├── MessageItem.tsx    # 消息气泡：把 [n] 引用解析为可点击 chip
    ├── SourcesPanel.tsx   # 右栏引用来源（点击打开源文件 + 核查徽标）
    ├── DocLibrary.tsx     # 文件库：上传/表格/标签/下载/删除
    └── AdminUsers.tsx     # 管理员：全部用户列表
```

## SSE 协议约定

`POST /api/chat` 返回 `text/event-stream`，每帧 `data: {…}\n\n`：

1. `{type:"sources", items:[{index,doc_name,section,source,preview}…]}` — 引用来源先到
2. `{type:"delta", text}` × N — 回答逐字增量
3. `{type:"checks", items:[{index,status:"supported"|"unsupported"|"unknown"}]}` — 引用核查
4. `{type:"done", session_id}` 或 `{type:"error", message}` — 结束

设计要点：来源先于正文展示降低等待感；`[n]` 引用在气泡内渲染为 chip，点击调用 `/api/open-file` 打开源文件；未通过核查的引用在来源卡片与气泡下方给出提示。
