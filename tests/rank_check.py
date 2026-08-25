"""临时诊断：对比不同查询变体下"入社条件"块的检索排名。"""
from memodoc.pipeline import Pipeline

GOLD = "入社条件"

p = Pipeline()
for q in ["我还需要交会费吗", "我是大一新生，我还需要交会费吗", "大一新生入社需要缴纳社费吗"]:
    print(f"== query: {q} ==")
    rs = p.retriever.retrieve(q, top_k=5)
    for r in rs:
        mark = " <== GOLD" if GOLD in r.section else ""
        print(f"   #{r.index} {r.score:.4f} {r.section.split('/')[-1]}{mark}")
