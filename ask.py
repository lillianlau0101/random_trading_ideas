"""第 3 步：生成。把检索到的条款交给 Claude，要求只依据条款回答并标注出处。

用法：python ask.py "主板股票的涨跌幅限制是多少？"
"""
import os
import re
import sys
import time

import anthropic

from retrieve import search

MODEL = os.environ.get("RAG_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("RAG_EFFORT", "low")  # low / medium / high：越高越准、越慢、越贵

SYSTEM = """你是 A 股交易规则助手，服务对象是券商和基金的交易、合规人员。

规则：
1. 只根据 <条款> 中提供的内容回答，不要使用你自己记忆中的规则。规则经常修订，你的记忆可能过时。
2. 每一个事实陈述后面都用 [编号] 标注出处，编号就是条款前面的数字，例如 [2]。
3. 如果提供的条款不足以回答，直接回答“现有条款中没有找到依据”，并说明缺的是哪方面信息。不要猜。
4. 上交所、深交所、港交所的规定不同时，分开说明。
5. 先给一句话结论，再给细节。用中文回答。"""

client = anthropic.Anthropic()


def build_context(hits):
    return "\n\n".join(
        f"<条款 编号=\"{i}\" 来源=\"{h['exchange']}《{h['doc']}》{h['article']}\">\n{h['text']}\n</条款>"
        for i, h in enumerate(hits, 1)
    )


def ask(question: str, k: int = 6):
    hits = search(question, k)
    start = time.time()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": EFFORT},
        # 安全分类器拒答时，由服务端自动换一个模型重试
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": f"{build_context(hits)}\n\n问题：{question}",
        }],
    )
    latency = time.time() - start

    if response.stop_reason == "refusal":
        answer = "（模型拒绝回答）"
    else:
        answer = "".join(b.text for b in response.content if b.type == "text")

    # 检查引用：只保留真实存在的编号，编出来的编号单独列出
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer)})
    sources = [hits[n - 1] for n in cited if 1 <= n <= len(hits)]
    bad_citations = [n for n in cited if not 1 <= n <= len(hits)]

    return {
        "question": question,
        "answer": answer,
        "sources": sources,
        "retrieved": hits,
        "bad_citations": bad_citations,
        "latency_s": round(latency, 1),
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "主板股票的涨跌幅限制是多少？"
    r = ask(q)
    print(r["answer"], "\n\n出处：")
    for s in r["sources"]:
        print(f"  {s['exchange']}《{s['doc']}》{s['article']}")
    if r["bad_citations"]:
        print(f"  ⚠ 引用了不存在的编号：{r['bad_citations']}")
    print(f"\n{r['latency_s']}s · 输入 {r['input_tokens']} tokens · 输出 {r['output_tokens']} tokens · {MODEL}")
