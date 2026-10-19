"""第 2 步：检索。给一个问题，找出最相关的 k 个条款。

v1 用 BM25（关键词检索）：不需要 embedding 模型，规则类文本关键词很强，效果不差。
v2 再换成向量检索（embedding），用 evals 对比两者的命中率。

单独测试：python retrieve.py "科创板涨跌幅限制"
"""
import json
import sys
from functools import lru_cache
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi

jieba.setLogLevel(60)
CHUNKS = Path("data/chunks.jsonl")


def tokenize(text: str):
    return [w for w in jieba.lcut(text.lower()) if w.strip()]


@lru_cache(maxsize=1)
def load_index():
    chunks = [json.loads(line) for line in CHUNKS.read_text(encoding="utf-8").splitlines()]
    # 把文档名也放进检索文本，问“深交所……”时能命中深交所的文件
    bm25 = BM25Okapi([tokenize(f"{c['exchange']} {c['doc']} {c['text']}") for c in chunks])
    return chunks, bm25


def search(query: str, k: int = 6):
    chunks, bm25 = load_index()
    scores = bm25.get_scores(tokenize(query))
    top = sorted(range(len(chunks)), key=lambda i: -scores[i])[:k]
    return [dict(chunks[i], score=round(float(scores[i]), 2)) for i in top]


if __name__ == "__main__":
    for hit in search(" ".join(sys.argv[1:]) or "涨跌幅限制"):
        print(f"[{hit['score']}] {hit['id']}\n    {hit['text'][:80]}…\n")
