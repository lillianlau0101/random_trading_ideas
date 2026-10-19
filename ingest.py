"""第 1 步：读取规则原文 → 繁体转简体 → 按条款切块 → 存成 data/chunks.jsonl

用法：python ingest.py
"""
import json
import re
from pathlib import Path

from docx import Document
from opencc import OpenCC
from pypdf import PdfReader

RAW = Path("data/raw")
OUT = Path("data/chunks.jsonl")
EXCHANGES = {"sse": "上交所", "szse": "深交所", "hkex": "港交所"}

# 港交所中文规则是繁体，统一转成简体，否则“涨跌幅”检索不到“漲跌幅”
T2S = OpenCC("t2s")

# 条款编号（必须在行首）：
#   沪深交易规则："3.1.2 投资者..."（章.节.条）或 "6.6 本所..."（第六章以后只有章.条），后面紧跟中文正文
#   沪深通实施办法："第十二条 ..."（编号后有空格；“第十八条规定的……”是交叉引用，不算）
#   港交所规则："1401. ..." / "14A06. ..."
#   港交所 FAQ："1.2. Are ..." / "1.3.1. What ..."
ARTICLE = re.compile(
    r"^\s*("
    r"第[一二三四五六七八九十百零〇\d]+条(?=\s)"
    r"|[1-9]\d?\.\d{1,2}(?:\.\d{1,2})?(?![\d.])(?!\s*条)(?=\s*[一-鿿])"
    r"|14[AB]?\d{2}[A-Z]?(?=\.)"
    r"|\d+\.\d+(?:\.\d+)?(?=\.\s+[A-Z])"
    r")"
)
# PDF 页眉页脚：“— 23 —”、“14A - 14”、单独一行的页码
PAGE_NOISE = re.compile(r"^\s*(—\s*\d+\s*—|14[AB]?\s*-\s*\d+|\d{1,3})\s*$")
# PDF 把一句中文切成多行，两边都是中文时直接拼回去
CJK_BREAK = re.compile(r"(?<=[一-鿿，、；（）“”《》\d%])\n(?=[一-鿿，、；。（）“”《》\d%])")
MAX_CHARS = 1500  # 单条太长时再切


def read_text(path: Path) -> str:
    if path.suffix == ".pdf":
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    elif path.suffix == ".docx":
        text = "\n".join(p.text for p in Document(path).paragraphs)
    else:
        text = path.read_text(encoding="utf-8")
    return T2S.convert(text)


def split_articles(text: str):
    """按条款编号切块。返回 [(条款号, 正文)]。第一个编号之前的内容（标题、修订沿革、目录）归为“开头”。"""
    articles, current_id, buf = [], "开头", []
    for line in text.splitlines():
        if not line.strip() or PAGE_NOISE.match(line):
            continue
        m = ARTICLE.match(line)
        if m:
            if buf:
                articles.append((current_id, "\n".join(buf)))
            current_id, buf = m.group(1), [line.strip()]
        else:
            buf.append(line.strip())
    if buf:
        articles.append((current_id, "\n".join(buf)))
    return articles


def to_chunks(path: Path, exchange: str):
    doc = T2S.convert(path.stem)
    for article, body in split_articles(read_text(path)):
        if path.suffix == ".pdf":
            body = CJK_BREAK.sub("", body)
        parts = [body[i:i + MAX_CHARS] for i in range(0, len(body), MAX_CHARS)]
        for n, part in enumerate(parts):
            suffix = f"-{n + 1}" if len(parts) > 1 else ""
            yield {
                "id": f"{exchange}|{doc}|{article}{suffix}",
                "exchange": EXCHANGES.get(exchange, exchange),
                "doc": doc,
                "article": article,
                "text": part,
            }


def main():
    chunks = []
    for folder in sorted(RAW.iterdir()):
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.suffix not in {".pdf", ".docx", ".txt"}:
                continue
            new = list(to_chunks(path, folder.name))
            print(f"{folder.name:5} {path.name}: {len(new)} 块")
            chunks += new
    if not chunks:
        print("data/raw/ 下没有找到文件，先按 sources.md 下载规则原文。")
        return
    ids = [c["id"] for c in chunks]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        print(f"⚠ {len(dupes)} 个重复编号，例如 {sorted(dupes)[:3]}（可能是正文里的交叉引用被当成了条款开头）")
    OUT.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in chunks), encoding="utf-8")
    print(f"共 {len(chunks)} 块 → {OUT}")


if __name__ == "__main__":
    main()
