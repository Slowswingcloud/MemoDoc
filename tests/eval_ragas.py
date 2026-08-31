"""RAGAS 端到端评测：faithfulness / response_relevancy / context_precision / context_recall。

两套测试集：
- demo_doc（受控中文文档，7 题）
- 英文论文跨语言（Agent-OS 论文，3 题，中文提问）

用法（推荐升级到 ragas 0.3，脚本自动兼容 0.2/0.3）：
    uv pip install -U ragas langchain-openai langchain-huggingface
    .venv\\Scripts\\python.exe tests\\eval_ragas.py

裁判 LLM：DeepSeek（OpenAI 兼容）；embedding：本地 bge-small-zh-v1.5。
原始结果保存到 data/eval/raw/ragas-<时间戳>.json（可复现，答辩证据）。
"""
from __future__ import annotations

import json
import sys
import time
import types
from pathlib import Path

from memodoc.config import settings
from memodoc.pipeline import Pipeline

QA_DEMO = [
    {"q": "加入极客社需要满足哪些条件？", "tags": ["演示"],
     "gold": "本校在读学生优先，需参加入社面试并缴纳社费30元/学期。"},
    {"q": "每周例会在什么时间、什么地点？", "tags": ["演示"],
     "gold": "每周三晚19:00-21:00在主教学楼B201教室。"},
    {"q": "无故缺席一次例会会被扣多少积分？", "tags": ["演示"],
     "gold": "无故缺席例会一次扣除3积分。"},
    {"q": "单次报销的金额上限是多少？", "tags": ["演示"],
     "gold": "单次报销金额上限200元，超过需提前向财务部申请。"},
    {"q": "担任一次主题分享主讲能获得多少积分？", "tags": ["演示"],
     "gold": "担任主题分享主讲可获得10积分。"},
    {"q": "技术部主要负责哪些工作？", "tags": ["演示"],
     "gold": "技术培训课程设计、校内编程比赛组织、官网与内部系统维护。"},
    {"q": "退社时已经缴纳的社费可以退还吗？", "tags": ["演示"],
     "gold": "退社时已缴纳的当学期社费不予退还。"},
]

QA_PAPER = [
    {"q": "Agent-OS论文提出了什么架构模型？", "tags": ["论文"],
     "gold": "五层 Agent-OS 模型，需求驱动规范（FR/NFR，NFR7 实时性），Agent Contract 用于可移植性。"},
    {"q": "Agent-OS论文如何设计安全机制？", "tags": ["论文"],
     "gold": "安全作为内核原语：RBAC 权限控制、能力限定的工具、加密内存、可审计追踪。"},
    {"q": "Agent-OS论文的动机是什么？", "tags": ["论文"],
     "gold": "当前 LM 代理系统缺乏操作系统级的调度、内存、实时响应与端到端安全保证。"},
]


def _load_embeddings():
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        from langchain_community.embeddings import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name=str(settings.model_dir))


def _shim_vertexai() -> None:
    """ragas 0.2 依赖已被 langchain-community 新版移除的 vertexai 模块 → 注入空 stub。"""
    if "langchain_community.chat_models.vertexai" in sys.modules:
        return
    try:
        import langchain_community.chat_models.vertexai  # noqa: F401

        return
    except ModuleNotFoundError:
        mod = types.ModuleType("langchain_community.chat_models.vertexai")
        mod.ChatVertexAI = type("ChatVertexAI", (), {})
        sys.modules["langchain_community.chat_models.vertexai"] = mod
        print("（已为 ragas 0.2 注入 vertexai 兼容 stub）")


def _print_scores(label: str, df) -> None:
    cols = [c for c in ("faithfulness", "response_relevancy", "answer_relevancy",
                        "context_precision", "context_recall") if c in df.columns]
    print(f"\n===== {label}（n={len(df)}）=====")
    if "question" in df.columns:
        print(df[["question"] + cols].to_string(index=False))
    print("\n平均分：")
    print(df[cols].mean().round(4))


def _collect(pipe: Pipeline, qa: list[dict], session: str) -> list[dict]:
    rows = []
    for item in qa:
        tags = item.get("tags")
        if tags and not pipe.vector_store.all_chunks(tags=tags):
            print(f"  ⚠ 标签 {tags} 内没有文档块——请先执行：memodoc tag <文档名> {' '.join(tags)}")
        retrieved = pipe.retriever.retrieve(item["q"], top_k=4, tags=item.get("tags"))
        ans = pipe.answer(session, item["q"], retrieved=retrieved)
        rows.append(
            {
                "question": item["q"],
                "answer": ans,
                "contexts": [r.text for r in retrieved],
                "ground_truth": item["gold"],
            }
        )
    return rows


def _evaluate(rows: list[dict], label: str, llm, embeddings):
    from datasets import Dataset

    ds = Dataset.from_list(rows)

    # ---- 优先 ragas 0.3（新 API）----
    try:
        from ragas import Ragas
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        try:
            from ragas.metrics import (
                ContextPrecision,
                ContextRecall,
                Faithfulness,
                ResponseRelevancy,
            )
        except ImportError:
            from ragas.metrics import (
                ContextPrecision,
                ContextRecall,
                Faithfulness,
            )
            from ragas.metrics import AnswerRelevancy as ResponseRelevancy

        evaluator = Ragas(
            metrics=[Faithfulness(), ResponseRelevancy(), ContextPrecision(), ContextRecall()],
            llm=LangchainLLMWrapper(llm),
            embeddings=LangchainEmbeddingsWrapper(embeddings),
        )
        try:
            result = evaluator.evaluate(ds)
        except AttributeError:
            result = evaluator.run(ds)
        df = result.to_pandas()
        _print_scores(label, df)
        return df
    except ImportError:
        pass

    # ---- 回退 ragas 0.2（旧 API + vertexai stub）----
    _shim_vertexai()
    from ragas import evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    result = evaluate(
        ds,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm,
        embeddings=embeddings,
    )
    df = result.to_pandas()
    _print_scores(label, df)
    return df


def main() -> None:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as e:
        print(f"缺少依赖：{e}\n请先执行：uv pip install -U ragas langchain-openai langchain-huggingface")
        return
    if not settings.llm_configured:
        print("未配置 DEEPSEEK_API_KEY，无法评测")
        return

    pipe = Pipeline()
    llm = ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0,
    )
    embeddings = _load_embeddings()

    demo_rows = _collect(pipe, QA_DEMO, "ragas")
    paper_rows = _collect(pipe, QA_PAPER, "ragas")

    demo_df = _evaluate(demo_rows, "demo_doc（受控中文）", llm, embeddings)
    paper_df = _evaluate(paper_rows, "英文论文（跨语言中文提问）", llm, embeddings)

    out = settings.data_dir / "eval" / "raw"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"ragas-{time.strftime('%Y%m%d-%H%M%S')}.json"
    payload = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "judge_llm": settings.deepseek_model,
        "embeddings": settings.embed_model,
        "qa_demo": demo_df.to_dict(orient="records"),
        "qa_paper": paper_df.to_dict(orient="records"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n原始结果已保存：", path)


if __name__ == "__main__":
    main()
