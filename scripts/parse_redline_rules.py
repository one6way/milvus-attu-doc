# -*- coding: utf-8 -*-
"""Спарсить правила REDLINE RP (rules.json) в JSONL-чанки для загрузки в Milvus.

Источник данных: https://redlinerp.ru/rules.json (страница правил подгружает его через js/rules.js).

Использование:
  # скачать исходник и распарсить
  python scripts/parse_redline_rules.py --url https://redlinerp.ru/rules.json --out data/redline_rules.jsonl
  # или из локального файла
  python scripts/parse_redline_rules.py --input rules.json --out data/redline_rules.jsonl

Формат строки вывода:
  {"text": "...", "section": "Раздел", "doc": "Документ", "chunk_index": 0, "source": "https://redlinerp.ru/rules.html"}

Затем загрузить в Milvus (см. scripts/load_jsonl_milvus.py):
  python scripts/load_jsonl_milvus.py --jsonl data/redline_rules.jsonl --collection redline_rules \
    --api-base http://127.0.0.1:1234/v1 --api-key sk-lm-... \
    --api-model text-embedding-nomic-embed-text-v1.5 \
    --doc-prefix "search_document: " --header-context \
    --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123 --recreate
"""
import argparse, io, json, re, sys, urllib.request

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("ERROR: нужен beautifulsoup4 + lxml.  pip install beautifulsoup4 lxml")

PAGE_URL = "https://redlinerp.ru/rules.html"
MAXLEN_DEFAULT = 900
OVERLAP_DEFAULT = 120


def clean_html(html):
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    txt = soup.get_text("\n")
    txt = re.sub(r"[ \t\r\f\v]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt)
    return txt.strip()


def chunk_card(body, section, doc, maxlen, overlap):
    paras = [p.strip() for p in body.split("\n") if p.strip()]
    out, buf, idx = [], "", 0
    for p in paras:
        while len(p) > maxlen:
            if buf:
                out.append({"text": buf, "section": section, "doc": doc, "chunk_index": idx})
                idx += 1
                buf = ""
            out.append({"text": p[:maxlen], "section": section, "doc": doc, "chunk_index": idx})
            idx += 1
            p = p[maxlen - overlap:]
            buf = ""
        if len(buf) + len(p) + 1 <= maxlen:
            buf = (buf + "\n" + p).strip()
        else:
            if buf:
                out.append({"text": buf, "section": section, "doc": doc, "chunk_index": idx})
                idx += 1
            buf = p
    if buf:
        out.append({"text": buf, "section": section, "doc": doc, "chunk_index": idx})
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="Правила REDLINE RP -> JSONL-чанки.")
    p.add_argument("--url", default=None, help="URL rules.json (по умолчанию — сайта REDLINE)")
    p.add_argument("--input", default=None, help="локальный rules.json (вместо --url)")
    p.add_argument("--out", required=True, help="куда писать jsonl")
    p.add_argument("--source", default=PAGE_URL, help="значение поля source")
    p.add_argument("--chunk-size", type=int, default=MAXLEN_DEFAULT)
    p.add_argument("--overlap", type=int, default=OVERLAP_DEFAULT)
    args = p.parse_args(argv)

    if args.input:
        raw = io.open(args.input, encoding="utf-8").read()
    else:
        url = args.url or "https://redlinerp.ru/rules.json"
        print(f"[1/3] скачиваю {url}", flush=True)
        raw = urllib.request.urlopen(url, timeout=30).read().decode("utf-8")
    data = json.loads(raw)

    rows = []
    for cat in data:
        section = cat.get("title", "")
        for card in cat.get("cards", []):
            doc = card.get("title", "")
            body = clean_html(card.get("body", ""))
            for ch in chunk_card(body, section, doc, args.chunk_size, args.overlap):
                ch["source"] = args.source
                rows.append(ch)

    with io.open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[3/3] разделов={len(data)} чанков={len(rows)} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())