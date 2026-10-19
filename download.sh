#!/usr/bin/env bash
# Download the official rule texts from SSE, SZSE and HKEX into data/raw/.
# The documents are not committed to this repo; they belong to the exchanges.
# Versions as of 2026-10-19. Check sources.md before relying on them.
set -euo pipefail
cd "$(dirname "$0")/data/raw"
mkdir -p sse szse hkex

HK=https://www.hkex.com.hk/-/media/HKEX-Market/Services/Rules-and-Forms-and-Fees/Rules/SEHK/Securities/Rules

get() { echo "→ $1"; curl -sSfL -A "Mozilla/5.0" -o "$1" "$2"; }

get "sse/上海证券交易所交易规则（2026年修订）.docx" \
  https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/10816482/files/e3a3b98e36894edca77841837936e006.docx
get "sse/上海证券交易所沪港通业务实施办法（2024年修订）.docx" \
  https://www.sse.com.cn/lawandrules/sselawsrules2025/global/hkexsc/c/10795123/files/2ad73fe12ffa4910b352ebceda89a23d.docx
get "szse/深圳证券交易所交易规则（2026年修订）.pdf" \
  https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf
get "szse/深圳证券交易所深港通业务实施办法（2024年修订）.pdf" \
  https://docs.static.szse.cn/www/lawrules/rule/inno/szhk/W020240614673497419312.pdf
get "hkex/HKEX 交易所规则 第十四章 中华通服务.pdf"        "$HK/Chap_14.pdf"
get "hkex/HKEX 交易所规则 第十四A章 中华通服务-上海.pdf"  "$HK/Chap_14a.pdf"
get "hkex/HKEX 交易所规则 第十四B章 中华通服务-深圳.pdf"  "$HK/Chap_14b.pdf"
get "hkex/HKEX Stock Connect FAQ.pdf" \
  https://www.hkex.com.hk/-/media/HKEX-Market/Mutual-Market/Stock-Connect/Getting-Started/Information-Booklet-and-FAQ/FAQ/FAQ_En.pdf

echo "Done. Next: python ingest.py"
