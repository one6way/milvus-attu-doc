# -*- coding: utf-8 -*-
"""Загрузка готовых чанков (JSONL с метаданными) в Milvus через API-эмбеддер.

Формат строки JSONL:
  {"text": "...", "section": "Раздел", "doc": "Документ", "chunk_index": 0, "source": "url"}

Пример:
  python scripts/load_jsonl_milvus.py --jsonl rules_chunks.jsonl --collection redline_rules \
    --api-base http://127.0.0.1:1234/v1 --api-key sk-lm-... \
    --api-model text-embedding-nomic-embed-text-v1.5 \
    --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123 --recreate
"""
import argparse, json, os, sys


def make_api_embedder(base_url, api_key, model_name, batch_size=64):
    import requests
    url = base_url.rstrip("/") + "/embeddings"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    print(f"[api] endpoint={url} model={model_name}", flush=True)

    def encode(texts):
        out = []
        for i in range(0, len(texts), batch_size):
            batch = list(texts[i:i + batch_size])
            try:
                resp = requests.post(url, headers=headers,
                                     json={"model": model_name, "input": batch}, timeout=180)
            except requests.exceptions.ConnectionError as e:
                raise SystemExit(f"ERROR: не удалось подключиться к {url}\n       {e}")
            if resp.status_code in (401, 403):
                raise SystemExit(f"ERROR: API {resp.status_code} (неверный --api-key): {resp.text[:200]}")
            if resp.status_code == 404:
                raise SystemExit(f"ERROR: API 404 для {url} — base должен оканчиваться на /v1")
            if resp.status_code != 200:
                raise SystemExit(f"ERROR: API {resp.status_code}: {resp.text[:300]}")
            data = resp.json()["data"]
            data.sort(key=lambda d: d.get("index", 0))
            out.extend([list(map(float, d["embedding"])) for d in data])
        return out

    return encode


def main(argv=None):
    p = argparse.ArgumentParser(description="Загрузка JSONL-чанков в Milvus (API-эмбеддер).",
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--jsonl", required=True)
    p.add_argument("--collection", required=True)
    p.add_argument("--api-base", default=os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:1234/v1"))
    p.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    p.add_argument("--api-model", default="text-embedding-nomic-embed-text-v1.5")
    p.add_argument("--batch", type=int, default=64)
    p.add_argument("--host", default=os.environ.get("MILVUS_HOST", "127.0.0.1"))
    p.add_argument("--port", default=os.environ.get("MILVUS_PORT", "19530"))
    p.add_argument("--user", default=os.environ.get("MILVUS_USER", ""))
    p.add_argument("--password", default=os.environ.get("MILVUS_PASSWORD", ""))
    p.add_argument("--metric", default="COSINE")
    p.add_argument("--index", default="AUTOINDEX")
    p.add_argument("--recreate", action="store_true")
    p.add_argument("--doc-prefix", default="",
                   help="префикс, добавляемый ТОЛЬКО к тексту при эмбеддинге документов "
                        "(для nomic-embed: 'search_document: '). В Milvus текст хранится без префикса.")
    p.add_argument("--header-context", action="store_true",
                   help="добавлять в текст эмбеддинга заголовок 'Раздел. Документ.' (улучшает попадание)")
    args = p.parse_args(argv)

    rows_in = []
    with open(args.jsonl, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows_in.append(json.loads(line))
    if not rows_in:
        raise SystemExit("ERROR: пустой jsonl")
    print(f"[1/3] строк={len(rows_in)}", flush=True)

    encode = make_api_embedder(args.api_base, args.api_key, args.api_model, args.batch)
    texts = [r["text"] for r in rows_in]

    def doc_embed_text(r):
        t = r["text"]
        if args.header_context:
            hdr = ". ".join(x for x in (r.get("section", ""), r.get("doc", "")) if x)
            if hdr:
                t = f"{hdr}. {t}"
        return (args.doc_prefix + t) if args.doc_prefix else t

    to_embed = [doc_embed_text(r) for r in rows_in]
    vectors = encode(to_embed)
    dim = len(vectors[0])
    print(f"[2/3] векторов={len(vectors)} dim={dim}", flush=True)

    from pymilvus import DataType, MilvusClient
    uri = args.host if args.host.startswith("http") else f"http://{args.host}:{args.port}"
    client = MilvusClient(uri=uri, token=(f"{args.user}:{args.password}" if args.user else ""))

    if client.has_collection(args.collection) and args.recreate:
        client.drop_collection(args.collection)
    if not client.has_collection(args.collection):
        schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dim)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="section", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="doc", datatype=DataType.VARCHAR, max_length=1024)
        schema.add_field(field_name="chunk_index", datatype=DataType.INT64)
        schema.add_field(field_name="source", datatype=DataType.VARCHAR, max_length=512)
        idx = client.prepare_index_params()
        idx.add_index(field_name="vector", index_type=args.index, metric_type=args.metric)
        print(f"[milvus] create {args.collection} dim={dim} metric={args.metric}", flush=True)
        client.create_collection(collection_name=args.collection, schema=schema, index_params=idx)

    data = []
    for r, vec in zip(rows_in, vectors):
        data.append({
            "vector": vec,
            "content": r["text"],
            "section": r.get("section", ""),
            "doc": r.get("doc", ""),
            "chunk_index": int(r.get("chunk_index", 0)),
            "source": r.get("source", ""),
        })
    res = client.insert(collection_name=args.collection, data=data)
    print(f"[3/3] вставлено={res.get('insert_count', len(data))} в {args.collection}", flush=True)
    try:
        client.load_collection(collection_name=args.collection)
        print(f"[milvus] collection {args.collection} загружена (Load)", flush=True)
    except Exception as e:
        print(f"[milvus] предупреждение: не удалось загрузить коллекцию: {e}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())