"""第 4 步：评估。用 evals/questions.jsonl 这套考卷给系统打分。

用法：
  python run_evals.py --retrieval-only              # 只测检索，不调用模型
  python run_evals.py                               # 默认模型
  RAG_MODEL=claude-haiku-5-5 python run_evals.py    # 换模型对比

四个指标，分开看才能知道问题出在哪一步：
  检索命中  —— 正确的文档有没有被找出来（检索的问题）
  答案正确  —— 回答里有没有关键事实（生成的问题）
  引用命中  —— 回答引用的出处是不是正确的文档
  拒答正确  —— 资料里没有的问题，有没有老实说“没找到”（幻觉控制）
"""
import json
import sys
import time
from pathlib import Path

from ask import MODEL, ask
from retrieve import search

QUESTIONS = Path("evals/questions.jsonl")
RESULTS = Path("evals/results")
REFUSAL = "没有找到依据"

# 每百万 token 的美元价格（2026-10 官网价，以 Anthropic 定价页为准）
PRICE = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


def has(answer: str, keyword: str) -> bool:
    """keyword 可以用 | 写多个等价写法，命中任意一个即可。"""
    text = answer.replace(" ", "")
    return any(k.replace(" ", "") in text for k in keyword.split("|"))


def grade(q, r):
    answer = r["answer"]
    if not q["answerable"]:
        return {"refused_ok": REFUSAL in answer}
    return {
        "retrieval_hit": any(q["doc"] in h["doc"] for h in r["retrieved"]),
        "correct": REFUSAL not in answer and all(has(answer, k) for k in q["expect"]),
        "citation_hit": any(q["doc"] in s["doc"] for s in r["sources"]),
    }


def pct(rows, key):
    vals = [row[key] for row in rows if key in row]
    return f"{sum(vals)}/{len(vals)}" if vals else "-"


def retrieval_only(questions, k=6):
    """不调用模型、不花钱，只看检索：正确文档和答案关键词有没有进 top-k。"""
    doc_hit = kw_hit = n = 0
    for q in questions:
        if not q["answerable"]:
            continue
        hits = search(q["question"], k)
        d = any(q["doc"] in h["doc"] for h in hits)
        kw = all(any(has(h["text"], keyword) for h in hits) for keyword in q["expect"])
        n, doc_hit, kw_hit = n + 1, doc_hit + d, kw_hit + kw
        print(f"{'✓' if d else '✗'}{'✓' if kw else '✗'} {q['id']} {q['question'][:30]}  →  "
              + ", ".join(f"{h['doc'][:6]}…{h['article']}" for h in hits[:3]))
    print(f"\n文档命中 {doc_hit}/{n} · 答案所在条款进入 top-{k} {kw_hit}/{n}")


def main():
    questions = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]
    if "--retrieval-only" in sys.argv:
        return retrieval_only(questions)
    rows = []
    for q in questions:
        r = ask(q["question"])
        g = grade(q, r)
        rows.append({**q, **g, **{k: r[k] for k in ("answer", "latency_s", "input_tokens", "output_tokens", "bad_citations")},
                     "sources": [s["id"] for s in r["sources"]]})
        mark = "✓" if g.get("correct", g.get("refused_ok")) else "✗"
        print(f"{mark} {q['id']} {q['question'][:30]}… ({r['latency_s']}s)")

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{MODEL}-{time.strftime('%Y%m%d-%H%M')}.jsonl"
    out.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")

    tin = sum(r["input_tokens"] for r in rows)
    tout = sum(r["output_tokens"] for r in rows)
    pin, pout = PRICE.get(MODEL, (0, 0))
    print(f"""
模型        {MODEL}
检索命中    {pct(rows, 'retrieval_hit')}
答案正确    {pct(rows, 'correct')}
引用命中    {pct(rows, 'citation_hit')}
拒答正确    {pct(rows, 'refused_ok')}
编造引用    {sum(len(r['bad_citations']) for r in rows)} 处
平均延迟    {sum(r['latency_s'] for r in rows) / len(rows):.1f}s
总成本      ${(tin * pin + tout * pout) / 1e6:.4f}（输入 {tin} / 输出 {tout} tokens）
明细        {out}""")


if __name__ == "__main__":
    main()
