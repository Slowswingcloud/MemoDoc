# MemoDoc 学习助手 · 前端（React + TypeScript）

> 小学期最终展示版前端：React 18 + TypeScript + Vite + Ant Design + Zustand。
> 消费 `api/server.py`（FastAPI）提供的 REST + SSE 接口；后端 RAG/Memory 逻辑未改动。

## 技术栈

| 层 | 选型 |
| --- | --- |
| 框架 | React 18 + TypeScript 5 |
| 构建 | Vite 5 |
| UI | Ant Design 5（主题定制）+ 自定义 CSS |
| 状态 | Zustand 4 |
| 流式 | 原生 fetch + ReadableStream 解析 SSE |

## 目录

```
frontend/
├── index.html / vite.config.ts / tsconfig*.json / package.json
└── src/
    ├── types.ts        # 共享类型（会话/消息/引用/文档/画像/统计/SSE 事件）
    ├── api.ts          # REST 封装 + SSE 流式客户端
    ├── store.ts        # Zustand 全局状态（角色/会话/消息/面板数据）
    ├── App.tsx         # 布局：头部(角色切换) + 侧栏 + 主区 + 右栏
    ├── styles.css      # 全局样式（渐变/卡片/气泡/滚动条）
    └── components/
        ├── Sidebar.tsx        # 会话列表（新对话/切换/删除）
        ├── ChatPanel.tsx      # 聊天主区（流式渲染/建议问题/输入）
        ├── MessageItem.tsx    # 消息气泡（[n] 引用 chip 可点击打开源文件）
        ├── SourcesPanel.tsx   # 右栏：引用来源（点击打开源文件 + 核查徽标）
        ├── ProfilePanel.tsx   # 右栏：学习画像（薄弱点/身份/偏好）
        ├── DocLibrary.tsx     # 教师：资料库（批量上传+分类+过滤+删除）
        └── StatsPanel.tsx     # 教师：班级薄弱点统计
```

## 运行

```bash
# 1) 安装依赖（首次）
cd frontend
npm install

# 2a) 开发模式（需要后端在 8000 端口：python server.py）
npm run dev            # http://127.0.0.1:5173 （/api 自动代理到 8000）

# 2b) 生产模式（构建后由 FastAPI 托管）
npm run build          # 产物在 frontend/dist
cd ..
python server.py       # http://127.0.0.1:8000 （FastAPI 直接托管 React 构建产物）
```

## 设计要点

- **角色视图**：学生 = 复习问答 + 学习画像；教师 = 课件问答 / 资料库管理 / 班级统计。
- **SSE 流式**：`POST /api/chat` 返回 `data: {type: sources|delta|checks|done|error}`，前端逐帧渲染。
- **引用可点击**：回答中的 `[n]` 渲染为 chip，点击调用 `/api/open-file` 用系统默认程序打开源文件。
- **学习画像**：学生问答后由后端单独抽取 `learning` 事实，右栏展示；教师端聚合为班级统计。
