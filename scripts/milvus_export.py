#!/usr/bin/env python3
"""Обратная выгрузка: коллекция Milvus -> текст (.txt / .jsonl / .docx).

Полезно, чтобы «вернуть» документ из векторов: Milvus хранит исходные чанки
(поле text или content), их можно собрать обратно в один файл.

Что делает:
  1. Находит текстовое поле (text|content) и поле chunk_index.
  2. Читает все строки, сортирует по chunk_index.
  3. Пишет результат в выбранный формат.

Примеры:
  python scripts/milvus_export.py --collection moskva_sem --out moskva_back.txt
  python scripts/milvus_export.py --collection moskva_ft  --out moskva_back.docx --format docx
  python scripts/milvus_export.py --collection moskva_sem --out moskva.jsonl --format jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Sequence

TEXT_FIELDS = ("text", "content")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Выгрузка коллекции Milvus обратно в текст",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--collection", required=True, help="имя коллекции")
    p.add_argument("--out", required=True, help="выходной файл (.txt/.jsonl/.docx)")
    p.add_argument("--format", choices=["txt", "jsonl", "docx"], default=None,
                   help="формат (по умолчанию по расширению --out)")
    p.add_argument("--text-field", default=None, help="поле с текстом (по умолчанию авто: text|content)")
    p.add_argument("--host", default=os.environ.get("MILVUS_HOST", "127.0.0.1"))
    p.add_argument("--port", default=os.environ.get("MILVUS_PORT", "19530"))
    p.add_argument("--user", default=os.environ.get("MILVUS_USER", ""))
    p.add_argument("--password", default=os.environ.get("MILVUS_PASSWORD", ""))
    return p


def detect_text_field(fields: Sequence[str], explicit: str | None) -> str:
    if explicit:
        if explicit not in fields:
            raise SystemExit(f"ERROR: поля {explicit!r} нет в схеме. Есть: {list(fields)}")
        return explicit
    for f in TEXT_FIELDS:
        if f in fields:
            return f
    raise SystemExit(f"ERROR: не найдено текстовое поле {TEXT_FIELDS}. Схема: {list(fields)}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        from pymilvus import MilvusClient
    except ImportError:
        print("ERROR: нужен pymilvus.  pip install -r scripts/requirements-vectorize.txt", file=sys.stderr)
        return 1

    fmt = args.format or os.path.splitext(args.out)[1].lstrip(".").lower() or "txt"
    if fmt == "json":
        fmt = "jsonl"

    uri = f"http://{args.host}:{args.port}"
    token = f"{args.user}:{args.password}" if args.password else ""
    client = MilvusClient(uri=uri, token=token) if token else MilvusClient(uri=uri)

    if not client.has_collection(args.collection):
        print(f"ERROR: коллекции {args.collection!r} нет. Есть: {client.list_collections()}", file=sys.stderr)
        return 1

    desc = client.describe_collection(args.collection)
    fields = [f["name"] for f in desc.get("fields", [])]
    tfield = detect_text_field(fields, args.text_field)
    has_idx = "chunk_index" in fields

    client.load_collection(args.collection)
    out_fields = [tfield] + (["chunk_index"] if has_idx else []) + (["source"] if "source" in fields else [])
    rows = client.query(args.collection, filter="", output_fields=out_fields, limit=16384)
    if has_idx:
        rows.sort(key=lambda r: r.get("chunk_index", 0))

    print(f"[milvus] {args.collection}: строк={len(rows)} текстовое поле={tfield} формат={fmt}", flush=True)

    if fmt == "jsonl":
        with open(args.out, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps({k: r[k] for k in r if k != "id"}, ensure_ascii=False) + "\n")
    elif fmt == "docx":
        try:
            from docx import Document
        except ImportError:
            print("ERROR: для docx нужен python-docx.  pip install -r scripts/requirements-vectorize.txt", file=sys.stderr)
            return 1
        doc = Document()
        for r in rows:
            for block in str(r[tfield]).split("\n"):
                doc.add_paragraph(block)
        doc.save(args.out)
    else:  # txt
        with open(args.out, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(str(r[tfield]).rstrip() + "\n\n")

    print(f"OK: {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())