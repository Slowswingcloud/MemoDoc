# RAG 手搓练习区（RAG Lab）

> 目标：不看我仓库里 `src/memodoc/rag/` 的实现，按下面的任务书从零手搓
> **BM25 → 混合融合 → 重排 → 引用核查** 四个组件。
> 完成后用 `verify.py` 自测，找我看点评。

## 规则（重要）

1. **先写自己的，再对照答案**。卡住时的参考顺序（由弱到强）：
   - a) 看 Kotaemon 源码：`../kotaemon-ref/`（BM25 看 `storages/docstores/elasticsearch.py`；混合检索看 `indices/vectorindex.py`；引用核查看 `indices/qa/citation.py`）；
   - b) 找我——**我只给思路和公式，不给代码**；
   - c) 最后才对照我的实现（`src/memodoc/rag/sparse.py` / `retriever.py` / `reranker.py` + `pipeline.check_citations`）。
2. **每搓完一步**：`python verify.py <步号>` 全绿 → git commit → 找我点评。
3. 只允许用：标准库 + `jieba`（已装）+ `sentence-transformers`（已装）+ `requests`。**禁止 import `memodoc` 的 rag 内部模块**（`verify.py` 会替你准备数据）。

## 通用接口契约（和项目一致，方便最后替换进去）

- 片段统一用 dict：`{"id": str, "text": str, "section": str, "score": float}`
- 你的模块放在本目录，函数签名以各 stub 文件为准。

---

## Step 1：BM25 稀疏检索（`bm25_index.py`）

**要理解**：倒排索引（term → 哪些片段 + 出现次数）；IDF（稀有词权重高）；BM25 公式：

```
score(d,q) = Σ idf(t) · f(t,d)·(k1+1) / (f(t,d) + k1·(1 − b + b·|d|/avgdl))
idf(t) = ln(1 + (N − df(t) + 0.5) / (df(t) + 0.5))      k1=1.5, b=0.75
```

**接口**：见 `bm25_index.py` 的 TODO。

**验证点**（`verify.py 1`）：
1. `tokenize("加入极客社需要满足哪些条件")` 返回非空列表；
2. 搜"社费"→ top 结果里含"社费"二字；
3. 搜"黑客松"→ top 结果含"黑客松"；
4. 稀有词查询（"黑客松"）的分数高于高频词查询（"社团"）的分数。

**进阶**（可选）：先只用字符 bigram 分词跑通，再升级 jieba，对比两种分词对验证点的影响。

---

## Step 2：混合融合（`fusion.py`）

**要理解**：为什么纯向量会漏（短查询、同义改写、专有名词）；为什么两种检索的分数不能直接相加（尺度不同）→ 各自 min-max 归一化到 [0,1] 再加权。

```
final_score = w · dense_norm + (1−w) · sparse_norm      w 默认 0.6
```

**接口**：`fuse(dense, sparse, w)`，见 `fusion.py`。

**验证点**（`verify.py 2`）：
1. 对 7 个评测问题，融合后 top-4 能召回对应 gold 片段（recall=100%）；
2. 融合分数都在 [0,1] 区间；
3. 输出按分数降序。

**进阶**（答辩加分）：再写一个 RRF 融合 `1/(k + rank)`，和加权融合对比差异。

---

## Step 3：交叉编码器重排（`reranker_lab.py`）

**要理解**：双塔（向量模型：句子→向量→相似度）vs **交叉编码器**（`(query, passage)` 拼一起过模型打分）——后者更准但慢，所以只对 top-N 候选重排。

**接口**：`RerankLab.rerank(query, candidates, top_k) -> candidates`，见 `reranker_lab.py`。

**验证点**（`verify.py 3`）：
1. 搜"每周例会在哪里开？"——重排前"每周例会"块排第 4，**重排后必须第 1**；
2. 其余 6 个评测问题重排后 gold 仍在 top-4。

---

## Step 4：引用核查（`citation_check.py`）

**要理解**：生成后验证——回答里的 `[n]` 真的被对应片段支持吗？用 LLM 当裁判。

**接口**：`check_citations(answer, chunks) -> {n: "supported"|"unsupported"|"unknown"}`，见 `citation_check.py`。

**验证点**（`verify.py 4`）：
1. 对一条"正确引用"的回答 → 判 supported；
2. 对一条"引用片段里没有的信息"的回答 → 判 unsupported。

**进阶**（可选）：先写启发式（引用句的关键词在片段中的覆盖率），再升级 LLM 裁判，对比两种方法的判断结果。

---

## 完成后的最后一步：替换进项目

四个组件全部通过后，把它们移植进 `src/memodoc/rag/`（替换我的实现），跑 `tests/eval.py` 三档对比。让我 review 你的移植。

## 时间参考（4h/天）

Step1 ≈ 1 天（纯数学最值得抠）→ Step2 ≈ 0.5 天 → Step3 ≈ 0.5 天 → Step4 ≈ 1 天 → 移植+评测 ≈ 1 天。
