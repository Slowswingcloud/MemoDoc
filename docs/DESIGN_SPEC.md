# MemoDoc 学习助手 — 详细设计说明书

> 说明：本文为产品演进设计稿（含 Gradio 版与学习画像/班级统计扩展设想）；main 分支 React 版实际实现了 user/admin + 问答/文件库/用户管理，画像/统计能力为后续演进方向。

- 版本：v1.0
- 依据：《MemoDoc 学习助手产品方案》（docs/PRODUCT_PLAN.md）、《系统架构说明》（docs/ARCHITECTURE.md）
- 适用范围：小学期项目开发、答辩演示、后续演进

---

## 1. 引言

### 1.1 编写目的
为"MemoDoc 学习助手"（基于文档 RAG 的长线学习平台）提供可指导编码的详细设计：模块划分、接口定义、数据结构、界面布局、关键流程、测试与验收标准。

### 1.2 项目背景
- 技术基础：已实现的 MemoDoc 核心——自研 RAG（手写 BM25 + 向量融合 + 交叉编码器重排 + 引用核查）+ mem0 式长期记忆 + Gradio UI（前端风格参考 GPT-Gradio-Agent）。
- 产品方向：教育私有化部署的长线学习助手，教师/学生双角色，文档与记忆长线维护。
- 设计原则：**一套知识库、两种视角**；现有 `src/` 核心不改，新增能力全部落在 UI 层与元数据/事实类型的小增量上。

### 1.3 术语
| 术语 | 含义 |
| --- | --- |
| RAG | 检索增强生成 |
| BM25 | 稀疏检索算法（手写实现，jieba 分词） |
| 重排（Rerank） | 交叉编码器对 (query, 片段) 精排（bge-reranker-v2-m3） |
| 引用核查 | 生成后由 LLM 验证每个 [n] 引用是否被片段支持 |
| 学习画像 | 记忆事实中的 `learning` 类型：薄弱知识点/掌握情况/常错题型 |
| 文档标签 | 文档元数据 `{course, doc_type}`，用于分类管理与过滤 |

### 1.4 参考资料
- docs/PRODUCT_PLAN.md（产品方案）
- docs/ARCHITECTURE.md（系统架构）
- README.md（快速开始）

---

## 2. 总体设计

### 2.1 设计目标
1. **功能**：教师上传/分类/管理资料并可问答与查看班级薄弱点；学生复习问答并被记住学习画像。
2. **性能**：单文档 < 100 块规模下，检索 + 生成首字延迟 < 30s（CPU 重排），流式输出。
3. **约束**：单机、离线可演示、数据本地存储（data/ 目录）、无需外部服务（ES/Milvus）。

### 2.2 系统架构（分层）

```
┌─────────────────────────────────────────────────────┐
│ UI 层：app.py（Gradio，GPT-Gradio-Agent 风格）        │
│   角色切换 → 学生端视图 | 教师端视图（共享知识库）     │
├─────────────────────────────────────────────────────┤
│ 编排层：pipeline.py（索引流 / 问答流 / 记忆流 / 统计） │
├──────────────┬──────────────┬───────────────────────┤
│ RAG 子系统    │ Memory 子系统 │ 基础设施               │
│ parser/chunk- │ extractor/   │ config/llm/session/   │
│ er/embedder/ │ store/       │ model/cli             │
│ sparse/store/│ injector     │                       │
│ retriever/   │ (+learning)  │                       │
│ reranker/    │              │                       │
│ generator    │              │                       │
└──────────────┴──────────────┴───────────────────────┘
```

### 2.3 模块清单
| 模块 | 文件 | 职责 | 本版本改动 |
| --- | --- | --- | --- |
| 配置 | `src/memodoc/config.py` | 全局配置 | 新增 doc_type 默认值等（少量） |
| LLM | `src/memodoc/llm/openai_compat.py` | DeepSeek chat/stream/json | 无 |
| 解析/分块 | `rag/parser.py` `rag/chunker.py` | PDF/MD/TXT → 标题感知分块 | 无 |
| 向量化 | `rag/embedder.py` | bge-small-zh | 无 |
| 稀疏检索 | `rag/sparse.py` | 手写 BM25 | 无 |
| 向量库/注册表 | `rag/store.py` | numpy 余弦 + JSON；DocumentRegistry | 注册表条目扩展 course/doc_type |
| 混合检索 | `rag/retriever.py` | dense+sparse 融合 + 重排 | 无 |
| 生成/引用核查 | `rag/generator.py` `pipeline.py` | 编号引用生成、check_citations | 无 |
| 记忆 | `memory/*.py` | 抽取/去重/注入 | extractor 增加 learning 类型 |
| 会话 | `session.py` | jsonl 历史 | 无 |
| 编排 | `pipeline.py` | 四类流（索引/问答/记忆/统计） | 新增：统计接口、文档分类元数据 |
| 模型下载 | `model.py` | embedding/reranker 下载 | 无 |
| UI | `app.py` | 三列布局 + 双角色 Tab | 大幅扩展（见 §5） |
| 评测 | `tests/eval.py` `tests/smoke.py` | 指标与冒烟 | 增加画像相关断言（可选） |

### 2.4 数据流
| 数据流 | 路径 | 触发 |
| --- | --- | --- |
| 索引流 | 文档(+标签) → 解析 → 分块 → 向量+BM25 → 注册表 | 教师上传 |
| 问答流 | 问题 → 记忆增强查询 → 双路召回 → 融合 → 重排 → 生成+引用 → 核查 | 学生/教师提问 |
| 记忆流 | 每轮后 LLM 抽取(身份/偏好/**学习**) → 去重/冲突更新 → 注入 | 学生问答后 |
| 统计流 | 聚合各学生 learning 事实 → 班级薄弱点统计 | 教师端查看 |

### 2.5 关键技术决策（及理由）
| 决策 | 理由 |
| --- | --- |
| 一套知识库 + 角色 flag，而非两套系统 | 共享 pipeline，工作量≈单角色；资料本身班级共有 |
| 角色切换而非真登录 | 7 天约束；答辩以"接入平台时由平台 SSO 认证，我们预留角色维度"说明 |
| 记忆事实新增 `learning` 类型 | 学生画像与教师统计共用同一份数据 |
| 统计只聚合不暴露个体 | 满足教育数据隐私叙事，答辩合规问题有答案 |
| 文档分类用元数据而非独立表 | 增量最小，与现有 DocumentRegistry 天然契合 |

---

## 3. 模块详细设计

### 3.1 config.py（新增配置）
```python
# 新增（带默认值，.env 可覆盖）
doc_types: list[str] = ["课件", "作业题", "往年题", "错题"]   # 文档类型枚举
default_course: str = "默认课程"
```

### 3.2 文档管理（store.py / pipeline.py 扩展）
**DocumentRegistry 条目扩展**：
```jsonc
{ "name": "软件工程课件1",
  "source": "data/uploads/xxx.md",
  "chunks": 24,
  "indexed_at": 1234.5,
  "course": "软件工程",
  "doc_type": "课件" }
```
**接口**：
```python
# store.py
class DocumentRegistry:
    def upsert(self, doc_name, source, chunks, course="默认课程", doc_type="课件") -> None
    def all(self, course: str | None = None, doc_type: str | None = None) -> list[dict]
    # 过滤在 all() 内做，返回子集

# pipeline.py
def index(self, path: str, course: str = "默认课程", doc_type: str = "课件") -> dict
    # 在现 index() 基础上把 course/doc_type 写入注册表（chunk meta 不变，避免重索引向量）
def documents(self, course=None, doc_type=None) -> list[dict]
```
**要点**：course/doc_type 只进注册表（documents.json），**不进 chunk 元数据**——避免改存储结构触发全量重索引；检索时仍跨全部文档（单班级场景）。

### 3.3 记忆子系统（learning 类型）
**事实模型**（不变）：
```jsonc
{ "type": "identity" | "preference" | "learning",
  "subject": "薄弱知识点" | "掌握情况" | "常错题型" | "...",
  "content": "对『状态图』的绘制掌握不足" }
```
**extractor.py 改动**：`_EXTRACT_SYSTEM` 增加第三类说明：
> learning：用户（学生）的学习状态，如薄弱知识点、掌握情况、常错题型。只抽取明确表达或可推断的内容。

**去重/冲突更新逻辑不变**（相似度 ≥0.85 去重；同 subject+type 且 0.6~0.85 替换）。

**画像面板数据接口**（pipeline 新增）：
```python
def learning_profile(self, user_id: str) -> list[dict]:
    """返回该用户全部 learning 事实，按时间倒序。"""
def class_stats(self) -> list[dict]:
    """聚合所有学生 learning 事实：{subject, content, count, users}，按 count 降序。"""
    # 实现：遍历 memory_store.all(user_id) for user_id in 学生集合
    # 按 (subject, content) 分组计数，users 记录出现的学生数
```

### 3.4 会话管理（session.py）
接口不变：`all / recent / list_sessions / delete / reset`。新增约定：
- 会话 id 前缀区分角色：`stu_<uuid>` / `tea_<uuid>`（UI 层生成，SessionStore 无感知）。

### 3.5 编排（pipeline.py）
现有接口保持不变（index/answer_stream/answer/check_citations/delete_doc/documents），新增：
```python
def index(self, path, course, doc_type) -> dict       # 见 3.2
def documents(self, course=None, doc_type=None)        # 见 3.2
def learning_profile(self, user_id) -> list[dict]      # 见 3.3
def class_stats(self) -> list[dict]                    # 见 3.3
```

### 3.6 UI（app.py，见 §5 详细布局）
新增组件与事件：
| 组件 | 事件 | 处理函数 |
| --- | --- | --- |
| 角色 Radio（学生/教师） | change | 切换 Tab 可见性 |
| 上传区：课程 Textbox + 类型 Dropdown | — | 随上传传入 index |
| 文档库过滤 Dropdown（课程/类型） | change | 过滤 doc_table |
| 学生端：学习画像面板 | — | 调 learning_profile 渲染 |
| 教师端：班级统计表 | — | 调 class_stats 渲染 |

---

## 4. 数据结构设计

### 4.1 文件存储布局
```
data/
├── uploads/            # 上传文件持久化（新增分类不改变此处）
├── store/
│   ├── docs.json       # 块向量库（不变）
│   ├── sparse.json     # BM25 索引（不变）
│   ├── memories.json   # 记忆事实（含新增 learning）
│   └── documents.json  # 文档注册表（新增 course/doc_type 字段）
└── sessions/           # 会话 jsonl（不变）
```

### 4.2 关键数据结构（不变 + 扩展）
| 结构 | 定义位置 | 字段 |
| --- | --- | --- |
| Chunk | chunker.py | id/text/doc_name/section_path/meta{section,source} |
| Retrieved | retriever.py | id/index/text/doc_name/section/score/source |
| 记忆事实 | memory/store.py | {type,subject,content,user_id,ts} |
| 文档条目 | store.py | {name,source,chunks,indexed_at, **course,doc_type**} |

---

## 5. 界面设计

### 5.1 总体布局（沿用 v3 三列网格）
```
┌─────────┬──────────────────────────────┬──────────────┐
│ 左：会话 │ 中：Tabs                       │ 右：面板      │
│ （角色   │  Tab1 学生端 / Tab2 教师端     │  引用来源     │
│  切换 +  │   （共享知识库）               │  长期记忆     │
│  会话列表）│                               │  /学习画像    │
└─────────┴──────────────────────────────┴──────────────┘
```

### 5.2 角色切换（左栏顶部）
`gr.Radio(["学生", "教师"], value="学生")` → change 事件控制各 Tab `visible`：
- 学生视图：Tab「复习问答」+「学习画像」
- 教师视图：Tab「课件问答」+「文档库管理」+「班级统计」

### 5.3 学生端视图
- **复习问答**：Chatbot + 输入 + 发送（复用现有 respond，`user_id="stu_xxx"`）；
- **学习画像**（右栏 Tab）：按 type 分组卡片（身份/偏好/学习），学习类高亮显示薄弱知识点。

### 5.4 教师端视图
- **文档库管理**：上传区（课程 Textbox + 类型 Dropdown + 多文件）+ 文档表（含课程/类型列）+ 过滤 Dropdown + 删除；
- **课件问答**：同一 Chatbot（`user_id="tea_xxx"`）或独立会话区；
- **班级统计**：`gr.Dataframe` 展示 {薄弱知识点, 出现次数, 涉及学生数}，按次数降序。

### 5.5 引用来源（右栏，师生共用）
维持现有可点击 Dataframe（点击行打开源文件）+ 引用核查徽标。

---

## 6. 关键流程设计

### 6.1 教师上传 + 分类索引
```
选择文件(多) + 输入课程 + 选类型 → 逐个 copy 到 data/uploads
→ pipeline.index(path, course, doc_type)（向量+BM25+注册表）
→ 刷新文档库（按当前过滤条件）
```

### 6.2 学生复习问答（记忆增强）
```
问题 → facts=memory.search(问题)（含 learning 事实）
→ 记忆拼进查询 → 双路召回 → 融合 → 重排 → 生成[引用]
→ 流式输出 → 引用核查 → LLM 抽取（identity/preference/learning）→ 去重入库
```

### 6.3 班级薄弱点统计
```
遍历学生 user_id → memory_store.all() 取 learning 事实
→ 按 (subject, content) 分组计数、统计涉及学生数
→ 按 count 降序 → 前端 Dataframe 展示
```

---

## 7. 测试与验收设计

### 7.1 单元/接口测试（tests/）
| 用例 | 期望 |
| --- | --- |
| `tokenize("加入极客社需要满足哪些条件")` | 非空、含"条件" |
| BM25 搜"社费" | 命中含"社费"的块 |
| `_fuse(dense, sparse, 0.6)` | 分数 ∈ [0,1] 且降序 |
| 重排"每周例会在哪里开？" | "每周例会"块第 1 |
| `check_citations` 正确/错误引用 | supported / unsupported |
| `learning_profile` / `class_stats` | 返回正确分组聚合 |

### 7.2 评测指标（tests/eval.py，不变）
三档 recall@4、引用准确率、关键词覆盖、引用核查通过率（基线 100%/100%/100%/100%）。

### 7.3 验收用例（对应 D1–D5）
| 天 | 验收 |
| --- | --- |
| D1 | 上传时能填课程/类型，文档库可按课程、类型过滤 |
| D2 | 角色一键切换，学生/教师 Tab 可见性正确 |
| D3 | 学生多轮问答后，学习画像出现"薄弱知识点"事实且无重复 |
| D4 | 教师端班级统计表正确聚合多个学生的薄弱点 |
| D5 | 完整演示剧本可连续走通（见 PRODUCT_PLAN §4） |

---

## 8. 部署与运行
- 环境：Python 3.12 venv（`uv`），依赖见 pyproject.toml；模型已本地化于 `data/models/`。
- 启动：`uv run python app.py` → http://127.0.0.1:7860
- 数据备份：备份 `data/store/*.json` 与 `data/uploads/` 即可迁移（全部为 JSON/文本，可审计）。
- 密钥：`.env` 中 DEEPSEEK_API_KEY（已配置）。

---

## 9. 风险与对策
| 风险 | 概率 | 对策 |
| --- | --- | --- |
| 时间不足 | 中 | 降级顺序：砍诊断面板 → 砍班级统计 → 保留核心问答+画像 |
| learning 抽取质量差 | 中 | 收窄到"薄弱知识点/掌握情况/常错题型"模板，few-shot 强化 |
| 角色切换影响现有会话 | 低 | 会话按 `stu_/tea_` 前缀隔离，互不干扰 |
| 长文本统计聚合慢 | 低 | 单班级规模（<50 学生），内存聚合即可 |
