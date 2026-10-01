#!/usr/bin/env python3
"""Конвертер .docx -> JSONL для ручного импорта в Attu (БЕЗ эмбеддинг-модели).

Что делает:
  1. Извлекает текст из .docx (абзацы + таблицы) и режет на чанки.
  2. Пишет JSONL: по одной строке на чанк вида
        {"text": "...", "source": "file.docx", "chunk_index": 0}
     Такой файл можно загрузить в Attu через "Import Data" (.json / .jsonl / .parquet).

Зачем без модели: Milvus 3.0 умеет ПОЛНОТЕКСТОВЫЙ поиск (BM25) — эмбеддинги не нужны,
Milvus сам строит sparse-векторы из текстового поля. Для семантического поиска
(по смыслу) нужна модель — см. README, раздел про поиск.

Пример:
  python scripts/docx_to_jsonl.py --file D:\\FILE_WORD\\file.docx --out file.jsonl --echo 1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vectorize_docx import extract_docx_parts, chunk_parts  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="docx -> JSONL для импорта в Attu (без модели)")
    p.add_argument("--file", required=True, help="путь к .docx")
    p.add_argument("--out", default=None, help="выходной .jsonl (по умолчанию <file>.jsonl)")
    p.add_argument("--text-field", default="text", help="имя текстового поля в JSONL")
    p.add_argument("--chunk-size", type=int, default=800, help="размер чанка (символы)")
    p.add_argument("--overlap", type=int, default=120, help="перекрытие чанков (символы)")
    p.add_argument("--echo", type=int, default=0, help="показать первую N строк")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not os.path.isfile(args.file):
        print(f"ERROR: файл не найден: {args.file}", file=sys.stderr)
        return 1

    out = args.out or os.path.splitext(args.file)[0] + ".jsonl"
    parts = extract_docx_parts(args.file)
    chunks = chunk_parts(parts, args.chunk_size, args.overlap)
    source = os.path.basename(args.file)

    with open(out, "w", encoding="utf-8") as f:
        for i, c in enumerate(chunks):
            f.write(json.dumps({args.text_field: c, "source": source, "chunk_index": i},
                               ensure_ascii=False) + "\n")

    print(f"OK: {out}  строк={len(chunks)} (блоков={len(parts)})", flush=True)
    if args.echo > 0:
        with open(out, encoding="utf-8") as f:
            for _ in range(args.echo):
                line = f.readline()
                if not line:
                    break
                print("  " + (line[:200] + "…" if len(line) > 200 else line.rstrip()), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())