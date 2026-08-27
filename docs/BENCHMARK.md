# MemoDoc 评测基准（Benchmark）接入指南

> 目的：为答辩提供"诚实、可复现、有对比"的指标。优先选**中文**、与**RAG+引用+记忆**贴合的基准。

## 0. 适配原则（先读）

- 你的管道形态是"上传文档 → 聊天问答（引用+记忆）"；学术基准是"语料 → 问答 → 评测"，接入需三步：**语料建索引 → 你的问答 → 评估打分**。
- 学术基准官方裁判多用 GPT-4；你换 **DeepSeek** 时，报告中注明裁判模型，对比只在你的三档检索方式之间自洽即可。
- 所有原始输出存 `data/eval/raw/`，可复现。

---

## 1. RAGAS —— 自数据端到端评测（推荐先做）

**测什么**：faithfulness（回答是否忠于检索片段）、answer_relevancy、context_precision / context_recall。

**为什么适合**：直接测"你的管道"，demo_doc 一组、英文论文一组，数字就是答辩要的"我的系统分数"。

**现成脚本**：`tests/eval_ragas.py`（已写好：DeepSeek 当裁判、本地 bge 当 embedding、两套测试集、结果自动存档到 `data/eval/raw/`）。

**运行**：
```bash
# 推荐升级到 ragas 0.3（0.2 与新版 langchain-community 不兼容，见 ragas#2741）
uv pip install -U ragas langchain-openai langchain-huggingface
.venv\Scripts\python.exe tests\eval_ragas.py
```
脚本自动兼容 ragas 0.2/0.3；若仍用 0.2，会自动注入 vertexai 兼容 stub。
**注意**：`context_recall` 的 ground_truth 与片段做语义匹配（LLM 判定），成本略高；若只想快跑，可只留 `faithfulness + answer_relevancy`。

---

## 2. RGB-zh —— 中文 RAG 四项能力（抗幻觉叙事）

**测什么**（[RGB 论文](https://huggingface.co/buckets/huggingchat/papers-content/tree/2309/2309.01431.md)）：
1. **Negative Rejection（拒答）**：无答案问题，系统应回答"文档中没有相关信息"——正好对应你的抗幻觉设计；
2. Noise Robustness（噪声鲁棒）：检索混入无关文档还能答对；
3. Information Integration（信息整合）：答案分散在多个片段；
4. Counterfactual Robustness（反事实鲁棒）：文档里是反常识设定也要服从文档。

**接入**：
```bash
git clone https://github.com/chen7002/RGB.git   # 官方实现
```
1. 取 RGB-zh 语料（每项能力一个文档集）；
2. `memodoc index <corpus>` 建索引；
3. 用你的问答流回答每道题；
4. 用 RGB 的评估 prompt + **DeepSeek** 当裁判打分（官方默认 GPT-4，替换 `OPENAI_API_KEY`/base_url 为 DeepSeek 即可）。

---

## 3. CRUD-RAG —— 全面中文 RAG 基准（时间充裕时补全）

**测什么**：[CRUD-RAG](https://github.com/yangxikun/CRUD_RAG) —— 7 类任务（知识问答/信息抽取/长文本理解/事实核查/意图识别/结构化生成/上下文重写）× 4 领域（电商/百科/医疗/法律）。

**接入**：与 RGB 同构（语料→索引→问答→裁判）；语料量大，建议只选 1–2 个领域（如百科+电商）跑子集。

---

## 4. C-MTEB 检索子集 —— embedding 选型依据（免费，本地跑）

**测什么**：中文 embedding 的检索/重排质量（bge 系列的主场）。

**接入**（[C-MTEB 说明](https://bge-model.com/tutorial/4_Evaluation/4.2.3.html)）：
```bash
pip install mteb
python -m mteb.run -m BAAI/bge-small-zh-v1.5 -t T2Retrieval DuRetrieval CmedqaRetrieval CMRC2018 CovidRetrieval Cshortq
```
**注意**：数据集从 HuggingFace 下载（走你代理）；CPU 较慢；结果可与 bge 官方榜单对比，写进"为什么选 bge-small-zh"。

---

## 5. 记忆方向（可选/延伸）

- **LoCoMo** / [EasyLoCoMo](https://github.com/playeriv65/EasyLocomo)：长对话记忆问答，对应你的记忆模块；成本高，答辩时间紧可跳过，用你自己的"跨会话记忆 A/B 演示"替代。

---

## 6. 推荐组合与答辩叙事

| 组合 | 输出 | 答辩话术 |
| --- | --- | --- |
| **RAGAS（demo_doc + 论文各一组）** | faithfulness/relevancy 分数 | "端到端可信度：我的管道在受控与论文场景下忠实度 X" |
| **RGB-zh 拒答子集** | 拒答率 | "抗幻觉：无答案问题不乱答" |
| **C-MTEB 检索** | 检索/重排分 | "选 bge-small-zh 的依据：它在中文检索基准上的表现" |
| （你自己的 eval.py） | 三档 recall / 引用准确率 / 核查通过率 | "检索升级效果的内部对比" |

**原则**：数字必须能对应到 `data/eval/raw/` 的原始输出；报告注明裁判模型与受控条件。
