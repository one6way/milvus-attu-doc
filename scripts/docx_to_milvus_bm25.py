#!/usr/bin/env python3
"""Загрузка .docx в Milvus как full-text коллекция (BM25). БЕЗ эмбеддинг-модели.

Что делает:
  1. Извлекает текст из .docx (абзацы + таблицы) и режет на чанки.
  2. Создаёт коллекцию с текстовым полем + функцией BM25 (Milvus сам строит
     sparse-векторы из текста) и индексом SPARSE_INVERTED_INDEX/BM25.
  3. Вставляет текст чанков (векторы НЕ нужны).
  4. Опционально показывает пример поиска по ключевым словам.

Модель не требуется: поиск идёт по совпадению слов (не по смыслу).

Пример:
  python scripts/docx_to_milvus_bm25.py --file D:\\FILE_WORD\\file.docx --collection docs_ft ^
      --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123 --demo
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vectorize_docx import extract_docx_parts, chunk_parts  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="docx -> Milvus BM25 full-text коллекция (без модели)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--file", required=True, help="путь к .docx")
    p.add_argument("--collection", default=None, help="имя коллекции (по умолчанию из имени файла)")
    p.add_argument("--chunk-size", type=int, default=800, help="размер чанка (символы)")
    p.add_argument("--overlap", type=int, default=120, help="перекрытие чанков (символы)")
    p.add_argument("--max-length", type=int, default=8192, help="max_length текстового поля")
    p.add_argument("--recreate", action="store_true", help="удалить и создать коллекцию заново")
    p.add_argument("--demo", action="store_true", help="выполнить пример поиска после загрузки")
    p.add_argument("--query", default="", help="поисковый запрос для --demo")
    p.add_argument("--host", default=os.environ.get("MILVUS_HOST", "127.0.0.1"))
    p.add_argument("--port", default=os.environ.get("MILVUS_PORT", "19530"))
    p.add_argument("--user", default=os.environ.get("MILVUS_USER", ""))
    p.add_argument("--password", default=os.environ.get("MILVUS_PASSWORD", ""))
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        from pymilvus import DataType, Function, FunctionType, MilvusClient
    except ImportError:
        print("ERROR: нужен pymilvus.  pip install -r scripts/requirements-vectorize.txt", file=sys.stderr)
        return 1

    if not os.path.isfile(args.file):
        print(f"ERROR: файл не найден: {args.file}", file=sys.stderr)
        return 1

    collection = args.collection or os.path.splitext(os.path.basename(args.file))[0].lower()

    print(f"[1/3] текст из {args.file}", flush=True)
    parts = extract_docx_parts(args.file)
    chunks = chunk_parts(parts, args.chunk_size, args.overlap)
    if not chunks:
        print("ERROR: в документе не найдено текста", file=sys.stderr)
        return 1
    print(f"      блоков={len(parts)} чанков={len(chunks)}", flush=True)

    uri = f"http://{args.host}:{args.port}"
    token = f"{args.user}:{args.password}" if args.password else ""
    client = MilvusClient(uri=uri, token=token) if token else MilvusClient(uri=uri)

    if client.has_collection(collection) and args.recreate:
        print(f"[milvus] drop {collection}", flush=True)
        client.drop_collection(collection)

    if not client.has_collection(collection):
        print(f"[2/3] create {collection} (BM25, без модели)", flush=True)
        schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("text", DataType.VARCHAR, max_length=args.max_length, enable_analyzer=True)
        schema.add_field("source", DataType.VARCHAR, max_length=512)
        schema.add_field("chunk_index", DataType.INT64)
        schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_function(Function(
            name="bm25_fn",
            function_type=FunctionType.BM25,
            input_field_names=["text"],
            output_field_names=["sparse"],
        ))
        index_params = client.prepare_index_params()
        index_params.add_index("sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25")
        client.create_collection(collection_name=collection, schema=schema, index_params=index_params)
    else:
        print(f"[2/3] коллекция {collection} уже есть (добавляю строки)", flush=True)

    source = os.path.basename(args.file)
    rows = [{"text": c, "source": source, "chunk_index": i} for i, c in enumerate(chunks)]
    res = client.insert(collection_name=collection, data=rows)
    client.flush(collection)
    client.load_collection(collection)
    inserted = int(res.get("insert_count", len(rows)))
    print(f"[3/3] вставлено {inserted} строк в {collection} (uri={uri})", flush=True)

    if args.demo:
        query = args.query or chunks[0][:60]
        hits = client.search(collection_name=collection, data=[query], anns_field="sparse",
                             limit=3, output_fields=["text", "chunk_index"])
        print(f"\nПОИСК (BM25): {query!r}", flush=True)
        for h in hits[0]:
            print(f"  score={h['distance']:.3f} chunk={h['entity']['chunk_index']}: "
                  f"{h['entity']['text'][:90].replace(chr(10), ' ')}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())