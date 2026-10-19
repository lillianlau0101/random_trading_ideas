# A-Share Trading Rules Copilot

**Cited answers to China A-share trading-rule questions, grounded in the official SSE, SZSE and HKEX (Stock Connect) rulebooks.**

[中文说明](#中文说明) · Python · Claude API · BM25 retrieval · eval-driven

---

## The problem

Trading desks, compliance teams and foreign investors routinely need answers like *"What's the price limit on a STAR Market stock?"* or *"Can I buy ChiNext shares through Shenzhen Connect?"*

General-purpose LLMs answer these from memory, and memory goes stale. The SSE and SZSE trading rules were both revised in **April 2026 (effective 6 July 2026)**: for example, the price limit on main-board risk-warning (ST) stocks moved from 5% to 10%, and after-hours fixed-price trading was extended to all A-shares and ETFs. A model trained before that will confidently give the old answer.

In a regulated workflow, *"probably 5%"* is worse than no answer. Users need **the answer, the clause it comes from, and an honest "not found" when the rules don't cover it.**

## What it does

```
question ─► retrieve top-6 clauses (BM25 over article-level chunks)
         ─► Claude answers ONLY from those clauses, citing [n] after every claim
         ─► citations are checked against what was actually retrieved
         ─► "现有条款中没有找到依据" when the clauses don't support an answer
```

**Corpus**: 8 official documents, 1,014 article-level chunks

| Exchange | Documents |
|---|---|
| SSE | Trading Rules (2026 rev.) · Shanghai Connect Implementation Measures (2024 rev.) |
| SZSE | Trading Rules (2026 rev.) · Shenzhen Connect Implementation Measures (2024 rev.) |
| HKEX | Rules of the Exchange Ch. 14 / 14A / 14B (China Connect Service) · Stock Connect FAQ (Jul 2026) |

## Design decisions

| Decision | Why |
|---|---|
| **Chunk by article, not by character count** | Citations point to a real clause (`3.3.13`, `第十八条`, `14A06`), and no rule gets cut in half. The chunker handles four numbering schemes: SSE/SZSE `3.1.2` and `6.6`, Connect measures `第X条`, HKEX `14A06.`, FAQ `1.2.` |
| **Ignore cross-references** | Lines like `第十八条规定的……` are references, not new articles. Treating them as article starts produced duplicate IDs, which the ingest step now detects and warns about. |
| **Traditional → Simplified conversion** | HKEX publishes Chinese rules only in Traditional characters. Without conversion, the query `涨跌幅` never matches `漲跌幅`. |
| **BM25 before embeddings** | Rule text is keyword-dense (`集合竞价`, `涨跌幅`), so BM25 is a strong, free, explainable baseline. Embeddings come next and are measured against it with the same eval. |
| **Citation validation** | The model must cite `[n]`; any number that doesn't map to a retrieved clause is flagged as a fabricated citation. |
| **Refusal is scored** | Out-of-scope questions (NYSE circuit breakers, future tax policy, SEC rules) only count as correct if the system says it found nothing. |

## Evaluation

The eval set is [`evals/questions.jsonl`](evals/questions.jsonl): 13 answerable questions plus 3 out-of-scope ones. Metrics are kept separate so a failure can be traced to the step that caused it:

| Metric | What it tells you |
|---|---|
| Retrieval hit | Was the right document retrieved? |
| Answer clause in top-k | Did the clause containing the answer make it into the context? |
| Answer correct | Does the answer contain the key fact? |
| Citation hit | Does the answer cite the right document? |
| Refusal correct | On out-of-scope questions, did it decline instead of guessing? |

### Current results: retrieval baseline (BM25, k=6)

| Metric | Score |
|---|---|
| Right document retrieved | **13 / 13** |
| Answer clause in top-6 | **9 / 13** |

End-to-end generation results (answer, citation and refusal accuracy, latency and cost per model) are not in yet. The runner is built: `python run_evals.py`.

### Failure analysis

The four retrieval misses are the useful part. Each is a textbook limitation of lexical search:

| Question | Where the answer is | Why BM25 missed it |
|---|---|---|
| SSE closing call auction hours | SSE 2.4.2 | Other clauses repeat "集合竞价" more often and outrank the one-line answer |
| Scope of after-hours fixed-price trading | SSE 3.7.1 (one sentence) | Query words like "2026年修订" and "适用于" pull in unrelated clauses |
| Investor requirements for STAR via Shanghai Connect | HKEX 14A06 | The rule says "机构专业投资者"; the question says "对投资者有什么要求". Same meaning, different words |
| Northbound daily quota | HKEX FAQ 1.6 (English) | Cross-lingual: a Chinese query can't match "RMB 52 billion" |

There is a subtler case too. For *"科创板股票的价格涨跌幅限制是多少"*, the top hit is SSE 6.12, a clause about price *deviation* that shares the keywords. The clause that actually sets the 20% limit (6.6) ranks lower. That's the argument for hybrid retrieval (BM25 + embeddings) plus a reranker.

## Quick start

```bash
git clone <this-repo> && cd a-share-rules-rag
python -m venv .venv && source .venv/bin/activate    # Python 3.10+
pip install -r requirements.txt

./download.sh                          # fetch the 8 official documents (not redistributed here)
python ingest.py                       # → data/chunks.jsonl
python retrieve.py 创业板 涨跌幅         # retrieval only, no API key needed
python run_evals.py --retrieval-only   # retrieval eval, free

export ANTHROPIC_API_KEY=...           # needed for the steps below
python ask.py "创业板股票的涨跌幅限制是多少？"
python run_evals.py                    # full eval
RAG_MODEL=claude-haiku-5-5 python run_evals.py   # compare models on cost/latency/accuracy
```

## Repo layout

| File | Role |
|---|---|
| `download.sh` | Fetch official rule texts into `data/raw/` |
| `ingest.py` | PDF/DOCX → Traditional-to-Simplified conversion → article-level chunks |
| `retrieve.py` | jieba tokenisation + BM25 |
| `ask.py` | Prompt assembly, Claude call, citation validation |
| `run_evals.py` | Eval runner: retrieval-only or end-to-end, with metrics, latency and cost |
| `evals/questions.jsonl` | Eval set. `verified: false` entries still need checking against source text |
| `sources.md` | Document versions, official URLs, download dates |

## Roadmap

- [ ] Run the end-to-end eval; compare Opus / Sonnet / Haiku on accuracy vs latency vs cost
- [ ] Hybrid retrieval (BM25 + multilingual embeddings) and reranking; target: answer clause in top-6 ≥ 12/13
- [ ] Grow the eval set to 50 questions, verified against source text
- [ ] Package as an MCP server so an exchange-announcement monitoring agent can call it
- [ ] Add CSRC Stock Connect regulations, STAR/ChiNext special rules, BSE trading rules

## Disclaimer

Educational project, not legal or investment advice. Rule texts belong to the respective exchanges and are fetched from their official sites rather than redistributed. Always check answers against the current official rules.

---

## 中文说明

**A 股交易规则 Copilot**：用上交所、深交所、港交所（中华通）的官方规则原文回答交易和合规问题。每个答案都标注条款出处，资料里没有的问题就明确回答“没找到”。

**为什么做**：沪深交易规则 2026 年 4 月修订，7 月 6 日起施行，比如主板风险警示股票的涨跌幅从 5% 调到 10%。大模型凭记忆回答，很可能给出旧版本，而交易和合规场景需要的是“依据哪一条”。

**怎么做**：

1. 按条款切块，兼容四种编号格式。
2. 港交所的繁体规则转成简体。
3. BM25 检索出 top-6 条款。
4. Claude 只依据这些条款作答，并用 [n] 标注出处。
5. 程序校验引用编号，编造的编号会被标出来。
6. 资料范围以外的问题，答“没找到”才算对。

**目前结果**：16 道题的考卷，检索阶段正确文档命中 13/13，答案所在条款进入 top-6 的有 9/13。没命中的 4 题分别属于关键词被稀释、同义不同词、跨语言等典型问题，是下一步升级混合检索的依据。端到端的生成评估（正确率、引用、拒答、成本）还没有跑。
