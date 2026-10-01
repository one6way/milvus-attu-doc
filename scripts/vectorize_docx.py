#!/usr/bin/env python3
"""Векторизация документа Word (.docx) и загрузка эмбеддингов в Milvus.

Что делает:
  1. Извлекает текст выбранного .docx (абзацы + таблицы).
  2. Режет текст на чанки заданного размера с перекрытием.
  3. Считает эмбеддинги:
       --embedder offline : локальная модель sentence-transformers (по умолчанию BAAI/bge-m3),
                            GPU если доступен (CUDA), иначе CPU. 0 токенов, оффлайн после 1-й загрузки.
       --embedder api     : внешний OpenAI-совместимый endpoint /embeddings (нужны --api-base/--api-key).
  4. Создаёт коллекцию в Milvus (если нет) и вставляет векторы + текст чанка.

Примеры:
  # только посмотреть чанки, без Milvus и без модели
  python scripts/vectorize_docx.py --file doc.docx --dry-run --echo-chunks 3

  # оффлайн bge-m3, Milvus через port-forward на 19530
  kubectl -n milvus port-forward svc/milvus 19530:19530
  python scripts/vectorize_docx.py --file doc.docx --collection my_doc

  # API-эмбеддер
  python scripts/vectorize_docx.py --file doc.docx --embedder api ^
      --api-base https://api.openai.com/v1 --api-model text-embedding-3-small
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import List, Sequence

DEFAULT_OFFLINE_MODEL = "BAAI/bge-m3"
DEFAULT_API_MODEL = "text-embedding-3-small"


# --------------------------------------------------------------------------- #
# 1. Извлечение текста из .docx
# --------------------------------------------------------------------------- #
def extract_docx_parts(path: str) -> List[str]:
    """Вернуть список текстовых блоков (абзацы + строки таблиц) из .docx."""
    try:
        from docx import Document  # python-docx
    except ImportError:
        raise SystemExit("ERROR: нужен python-docx.  pip install -r scripts/requirements-vectorize.txt")

    if not os.path.isfile(path):
        raise SystemExit(f"ERROR: файл не найден: {path}")

    doc = Document(path)
    parts: List[str] = []
    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if text:
            parts.append(text)
    for table in doc.tables:
        for row in table.rows:
            cells = [(c.text or "").strip() for c in row.cells]
            cells = [c for c in cells if c]
            if cells:
                parts.append(" | ".join(cells))
    return parts


# --------------------------------------------------------------------------- #
# 2. Чанкинг (чистая логика, не зависит от моделей)
# --------------------------------------------------------------------------- #
def _split_long(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Разбить слишком длинный блок на куски с перекрытием (в символах)."""
    out: List[str] = []
    step = max(1, chunk_size - overlap)
    i, n = 0, len(text)
    while i < n:
        out.append(text[i:i + chunk_size])
        if i + chunk_size >= n:
            break
        i += step
    return out


def chunk_parts(parts: Sequence[str], chunk_size: int = 800, overlap: int = 120) -> List[str]:
    """Собрать блоки в чанки <= chunk_size символов, стараясь не рвать абзацы."""
    if chunk_size <= 0:
        raise ValueError("chunk_size должен быть > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap должен быть >= 0 и < chunk_size")

    chunks: List[str] = []
    buf = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) > chunk_size:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(_split_long(part, chunk_size, overlap))
            continue
        candidate = f"{buf}\n\n{part}" if buf else part
        if len(candidate) <= chunk_size:
            buf = candidate
        else:
            chunks.append(buf)
            tail = buf[-overlap:] if overlap > 0 else ""
            buf = f"{tail}\n\n{part}" if tail else part
    if buf:
        chunks.append(buf)
    return chunks


# --------------------------------------------------------------------------- #
# 3. Эмбеддеры
# --------------------------------------------------------------------------- #
def make_offline_embedder(model_name: str, device: str = "auto", batch_size: int = 32):
    """Локальный эмбеддер на sentence-transformers. Возвращает (callable, dim)."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise SystemExit(
            "ERROR: --embedder offline требует sentence-transformers.\n"
            "       pip install -r scripts/requirements-vectorize.txt"
        )

    import torch  # type: ignore

    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda"
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"

    print(f"[offline] model={model_name} device={device}", flush=True)
    model = SentenceTransformer(model_name, device=device)
    dim = int(model.get_sentence_embedding_dimension())

    def encode(texts: Sequence[str]) -> List[List[float]]:
        vecs = model.encode(
            list(texts),
            batch_size=batch_size,
            normalize_embeddings=True,  # -> косинус == внутреннее произведение
            show_progress_bar=False,
        )
        return [list(map(float, v)) for v in vecs]

    return encode, dim


def make_api_embedder(base_url: str, api_key: str, model_name: str, batch_size: int = 64):
    """Эмбеддер через OpenAI-совместимый POST {base}/embeddings.

    Работает с OpenAI, Ollama (/v1), TEI (/v1), LM Studio и др.
    Возвращает (callable, dim=None) — dim узнаём из первого ответа.
    """
    try:
        import requests
    except ImportError:
        raise SystemExit("ERROR: --embedder api требует requests.  См. requirements-vectorize.txt")

    url = base_url.rstrip("/") + "/embeddings"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    print(f"[api] endpoint={url} model={model_name}", flush=True)

    def encode(texts: Sequence[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = list(texts[i:i + batch_size])
            resp = requests.post(
                url, headers=headers, json={"model": model_name, "input": batch}, timeout=180
            )
            if resp.status_code != 200:
                raise SystemExit(f"ERROR: API {resp.status_code}: {resp.text[:300]}")
            data = resp.json()["data"]
            data.sort(key=lambda d: d.get("index", 0))
            out.extend([list(map(float, d["embedding"])) for d in data])
        return out

    return encode, None


# --------------------------------------------------------------------------- #
# 4. Milvus
# --------------------------------------------------------------------------- #
def milvus_uri(host: str, port: str) -> str:
    """Собрать URI для MilvusClient (http://host:port)."""
    if host.startswith("http://") or host.startswith("https://"):
        return host if host.endswith(port) else f"{host}:{port}"
    return f"http://{host}:{port}"


def store_in_milvus(uri: str, token: str, collection: str, vectors: List[List[float]],
                    chunks: List[str], source: str, metric: str, dim: int,
                    index_type: str, recreate: bool) -> int:
    """Создать коллекцию (если нужно) и вставить строки. Вернуть число вставленных."""
    try:
        from pymilvus import DataType, MilvusClient
    except ImportError:
        raise SystemExit("ERROR: нужен pymilvus.  pip install -r scripts/requirements-vectorize.txt")

    client = MilvusClient(uri=uri, token=token) if token else MilvusClient(uri=uri)

    existing = client.has_collection(collection)
    if existing and recreate:
        print(f"[milvus] drop существующей коллекции {collection}", flush=True)
        client.drop_collection(collection)
        existing = False

    if not existing:
        schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dim)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="source", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="chunk_index", datatype=DataType.INT64)

        index_params = client.prepare_index_params()
        index_params.add_index(field_name="vector", index_type=index_type, metric_type=metric)

        print(f"[milvus] create collection={collection} dim={dim} metric={metric} index={index_type}", flush=True)
        client.create_collection(collection_name=collection, schema=schema, index_params=index_params)

    rows = [
        {"vector": vec, "content": text, "source": source, "chunk_index": i}
        for i, (vec, text) in enumerate(zip(vectors, chunks))
    ]
    res = client.insert(collection_name=collection, data=rows)
    return int(res.get("insert_count", len(rows)))
# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Векторизация .docx и загрузка в Milvus (offline sentence-transformers или API/TEI).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--file", required=True, help="путь к .docx")
    p.add_argument("--collection", default=None, help="имя коллекции Milvus (по умолчанию из имени файла)")
    p.add_argument("--dry-run", action="store_true", help="только извлечь и нарезать, без эмбеддингов и Milvus")
    p.add_argument("--echo-chunks", type=int, default=0, help="показать первые N чанков")
    p.add_argument("--chunk-size", type=int, default=800, help="размер чанка в символах")
    p.add_argument("--overlap", type=int, default=120, help="перекрытие между чанками в символах")

    p.add_argument("--embedder", choices=["offline", "api"], default="offline")
    p.add_argument("--model", default=DEFAULT_OFFLINE_MODEL, help="модель для --embedder offline")
    p.add_argument("--device", default="auto", help="cpu|cuda|mps|auto (только offline)")
    p.add_argument("--api-base", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                   help="base URL для --embedder api (OpenAI/Ollama/TEI/LM Studio)")
    p.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""), help="ключ для --embedder api")
    p.add_argument("--api-model", default=DEFAULT_API_MODEL)
    p.add_argument("--batch", type=int, default=32, help="размер батча эмбеддинга")

    p.add_argument("--host", default=os.environ.get("MILVUS_HOST", "127.0.0.1"))
    p.add_argument("--port", default=os.environ.get("MILVUS_PORT", "19530"))
    p.add_argument("--user", default=os.environ.get("MILVUS_USER", ""))
    p.add_argument("--password", default=os.environ.get("MILVUS_PASSWORD", ""))
    p.add_argument("--metric", default="COSINE", help="COSINE|L2|IP")
    p.add_argument("--index", default="AUTOINDEX", help="AUTOINDEX|HNSW|FLAT|...")
    p.add_argument("--recreate", action="store_true", help="удалить и создать коллекцию заново")
    return p
def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    print(f"[1/4] извлечение текста: {args.file}", flush=True)
    parts = extract_docx_parts(args.file)
    if not parts:
        print("ERROR: в документе не найдено текста", file=sys.stderr)
        return 1

    chunks = chunk_parts(parts, args.chunk_size, args.overlap)
    total_chars = sum(len(c) for c in chunks)
    print(f"      блоков={len(parts)} чанков={len(chunks)} символов={total_chars}", flush=True)

    if args.echo_chunks > 0:
        for i, c in enumerate(chunks[:args.echo_chunks]):
            preview = c if len(c) <= 200 else c[:200] + "…"
            print(f"      #{i} ({len(c)} симв.): {preview}", flush=True)

    if args.dry_run:
        print("[dry-run] остановлено до эмбеддингов/Milvus.", flush=True)
        return 0

    collection = args.collection or os.path.splitext(os.path.basename(args.file))[0].lower()

    print(f"[2/4] эмбеддинги ({args.embedder})", flush=True)
    t0 = time.time()
    if args.embedder == "offline":
        encode, dim = make_offline_embedder(args.model, args.device, args.batch)
    else:
        encode, dim = make_api_embedder(args.api_base, args.api_key, args.api_model, max(1, args.batch * 2))
    vectors = encode(chunks)
    if dim is None:
        dim = len(vectors[0])
    print(f"      векторов={len(vectors)} dim={dim} за {time.time() - t0:.1f}s", flush=True)

    print("[3/4] запись в Milvus", flush=True)
    token = f"{args.user}:{args.password}" if args.password else ""
    uri = milvus_uri(args.host, args.port)
    inserted = store_in_milvus(
        uri=uri, token=token, collection=collection, vectors=vectors, chunks=chunks,
        source=os.path.basename(args.file), metric=args.metric, dim=dim,
        index_type=args.index, recreate=args.recreate,
    )

    print(f"[4/4] готово: коллекция={collection} вставлено={inserted} uri={uri}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())