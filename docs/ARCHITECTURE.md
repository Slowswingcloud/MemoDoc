# MemoDoc 架构说明

## 1. 总架构

```mermaid
flowchart TB
    subgraph UI["界面层"]
        G["Gradio Web UI<br/>上传文档/提问/流式回答/引用高亮/记忆面板"]
    end

    subgraph CORE["编排层"]
        P["pipeline.py<br/>索引流 / 问答流 / 记忆流 三条链路"]
    end

    subgraph RAG["RAG 子系统（Kotaemon 系）"]
        R1["DocumentParser<br/>PDF/MD/TXT → 文本"]
        R2["Chunker<br/>标题感知分块"]
        R3["Embedder<br/>本地 bge-small-zh"]
        R4["VectorStore<br/>numpy 余弦 + JSON 持久化"]
        R5["Retriever<br/>向量检索 Top-K"]
        R6["Generator<br/>DeepSeek 流式 + 引用"]
    end

    subgraph MEM["Memory 子系统（mem0 系）"]
        M1["FactExtractor<br/>LLM 抽取结构化事实"]
        M2["MemoryStore<br/>向量库 + 冲突去重"]
        M3["MemoryInjector<br/>新会话注入相关记忆"]
    end

    subgraph INFRA["基础设施"]
        L["llm/openai_compat.py<br/>DeepSeek/Kimi 统一客户端"]
        S["session.py<br/>会话历史 jsonl"]
        C["config.py<br/>pydantic 配置"]
    end

    G -->|"提问/上传"| P
    P --> R5 --> R4
    R1 --> R2 --> R3 --> R4
    P --> R6 --> L
    P --> M3 --> M2
    P -->|"每轮后"| M1 --> M2
    P --> S
```

## 2. 三条数据流

| 数据流 | 路径 | 说明 |
| --- | --- | --- |
| 索引流 | 文档 → Parser → Chunker → Embedder → 向量库 | "把知识存进去"，上传时触发 |
| 问答流 | 问题 → [系统提示 + 相关记忆 + 会话历史 + 检索片段] → LLM 流式生成 + [n] 引用 | "带着知识和记忆回答" |
| 记忆流 | 每轮后 → LLM 抽取事实（身份/偏好）→ 去重/冲突更新入库；新会话 → 相关记忆注入 | "跨会话记住你"（mem0 基因） |

## 3. 模块清单

```
src/memodoc/
├── config.py             # pydantic-settings 配置（.env / 环境变量）
├── llm/openai_compat.py  # DeepSeek/Kimi 统一客户端（chat / stream / json）
├── rag/
│   ├── parser.py         # PyMuPDF + 文本解析
│   ├── chunker.py        # 标题感知分块（滑窗 + 重叠）
│   ├── embedder.py       # bge-small-zh 本地向量化（失败自动降级）
│   ├── store.py          # 自研向量库（numpy 余弦 + JSON 持久化）
│   ├── retriever.py      # Top-K 检索 + 关键词兜底
│   └── generator.py      # 系统提示 + 强制 [n] 引用
├── memory/
│   ├── extractor.py      # LLM 抽取结构化事实
│   ├── store.py          # 记忆向量库 + 去重 + 冲突更新
│   └── injector.py       # 新会话注入相关记忆
├── session.py            # 会话历史 jsonl
├── pipeline.py           # 三条链路编排
└── cli.py                # 命令行入口
```

## 4. 关键实现细节

- **引用编号与来源一一对应**：检索结果按顺序编号 `[1..k]` 写进系统提示；生成文本里的 `[n]` 直接映射回第 n 个片段，UI 据此高亮来源，从机制上避免"乱标来源"。
- **记忆去重**：新事实向量化后与库中最近邻比较，相似度 ≥ 0.85 判为重复跳过；同 `subject` 且同 `type` 判为冲突，用新事实替换旧事实。
- **降级链路**：embedding 模型不可用 → 自动回退字符 bigram 关键词检索，保证"没有模型也能演示"。
- **为什么不用 ChromaDB**：本机无 MSVC 构建工具，ChromaDB 依赖的 chroma-hnswlib 无 Windows/3.12 预编译 wheel（需源码编译）。演示规模（数百块）下 O(n) 精确检索毫秒级完成，JSON 存储可审计、零原生依赖；`store.py` 接口与 ChromaDB 对齐，后续可无缝替换。

## 5. 诚实的效果预期

- **可保证**：架构跑通——全部是成熟库拼装，无未验证技术。
- **高把握**：7 天内完成 v1（前提是每日 4–6h 投入）。
- **不保证、也不需要保证**：效果上限（引用准确率多高、回答多好）。答辩要的是"架构清晰 + 引用真实 + 指标诚实"，用受控演示剧本锁定效果，不赌运气。
