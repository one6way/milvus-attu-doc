"""Замеры для таблиц 3.1-3.4 и 3.6.5-3.6.6 (скрипт, которого не было в исходной редакции).

Что измеряется:
  * 3.6.2 — влияние efConstruction: время построения индекса, время поиска, Recall@10;
  * 3.6.3 — влияние ef: время поиска и Recall@10;
  * 3.6.4 — сравнение индексов FLAT / IVF_FLAT / IVF_SQ8 / HNSW: построение, поиск, Recall@10, память;
  * 3.6.5 — влияние скалярной фильтрации на время поиска;
  * 3.6.6 — сравнение метрик L2 / IP / COSINE (совпадение ранжирования на нормированных векторах
            и различие на НЕнормированных).

Ключевая деталь методики: эмбеддинги НЕ генерируются. Оценивается индекс и поиск, а не качество
модели, поэтому используются синтетические векторы размерности 768, нормализованные до единичной
длины (как их выдаёт intfloat/multilingual-e5-base с normalize_embeddings=True). Это на порядки
быстрее и делает замер воспроизводимым.

Ground truth (эталон) — точный поиск FLAT с той же метрикой; Recall@k = |A_approx ∩ A_exact| / k.

Запуск:
    python .\\verify\\benchmark.py --n 50000 --queries 100 --runs 5 --warmup 20
Быстрая проверка корректности:
    python .\\verify\\benchmark.py --n 5000 --queries 20 --runs 1 --warmup 3

Результат: verify/benchmark.log (UTF-8) и verify/benchmark_result.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DataType, client, drop_if_exists, start_log  # noqa: E402

DIM = 768
FIELD = "vec"
K = 10
MILVUS_CONTAINER = "milvus-standalone"
OPERATION_TYPES = ["purchase", "withdrawal", "transfer", "deposit"]
MCCS = ["5411", "4900", "4829", "5814"]

def container_mem_mb(container: str = MILVUS_CONTAINER):
    """RSS контейнера Milvus в МБ (столбец «Память»). None, если docker недоступен."""
    try:
        out = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container],
            capture_output=True, text=True, timeout=60,
        ).stdout.strip()
        used = out.split("/")[0].strip()
        value = float("".join(ch for ch in used if ch.isdigit() or ch == "."))
        if "GiB" in used:
            value *= 1024
        elif "KiB" in used:
            value /= 1024
        return round(value, 1)
    except Exception:  # noqa: BLE001 — замер памяти не критичен
        return None


def make_schema(c, name: str):
    schema = c.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field(FIELD, DataType.FLOAT_VECTOR, dim=DIM)
    schema.add_field("operation_type", DataType.VARCHAR, max_length=20)
    schema.add_field("mcc", DataType.VARCHAR, max_length=4)
    schema.add_field("amount_minor", DataType.INT64)
    c.create_collection(collection_name=name, schema=schema)


def build_rows(vectors: np.ndarray, rng: np.random.Generator) -> list[dict]:
    """Строки для вставки: вектор + скалярные поля (для проверки фильтрации).

    Тип операции и MCC назначаются независимо (случайно), чтобы комбинированный фильтр
    действительно отбирал подмножество, а не пустое множество.
    """
    rows = []
    for i, vec in enumerate(vectors):
        rows.append({
            "id": i,
            FIELD: vec.tolist(),
            "operation_type": OPERATION_TYPES[int(rng.integers(0, len(OPERATION_TYPES)))],
            "mcc": MCCS[int(rng.integers(0, len(MCCS)))],
            "amount_minor": int(rng.integers(1000, 2_000_000)),
        })
    return rows


def insert_all(c, name: str, rows: list[dict], batch: int = 5000) -> float:
    t0 = time.perf_counter()
    for start in range(0, len(rows), batch):
        c.insert(collection_name=name, data=rows[start:start + batch])
    c.flush(collection_name=name)
    return round(time.perf_counter() - t0, 1)


def build_index(c, name: str, index_type: str, metric: str, params: dict | None = None) -> float:
    """Снять текущий индекс и построить новый. Возвращает время построения, с."""
    c.release_collection(collection_name=name)
    for index_name in index_names(c, name):
        c.drop_index(collection_name=name, index_name=index_name)
    index_params = c.prepare_index_params()
    index_params.add_index(field_name=FIELD, index_type=index_type,
                           metric_type=metric, params=params or {})
    t0 = time.perf_counter()
    c.create_index(collection_name=name, index_params=index_params)   # дожидается построения
    return round(time.perf_counter() - t0, 1)


def load_index(c, name: str):
    """Загрузить коллекцию в память. Возвращает (время загрузки, с; занятая память, МБ — оценка).

    Память = RSS контейнера Milvus после загрузки минус RSS до загрузки (коллекция выгружена),
    то есть объём данных вместе с индексом в оперативной памяти.
    """
    mem_idle = container_mem_mb()
    t0 = time.perf_counter()
    c.load_collection(collection_name=name)
    load_s = round(time.perf_counter() - t0, 1)
    mem_loaded = container_mem_mb()
    mem = None if mem_idle is None or mem_loaded is None else round(mem_loaded - mem_idle, 1)
    return load_s, mem


def set_index(c, name: str, index_type: str, metric: str, params: dict | None = None):
    """Построить индекс и загрузить коллекцию (без замеров) — для подготовки эталона."""
    build_index(c, name, index_type, metric, params)
    load_index(c, name)


def run_search(c, name: str, queries: np.ndarray, metric: str,
               ef: int | None = None, expr: str = "", nprobe: int | None = None, k: int = K):
    """Поиск пакетом queries. Возвращает (время на один запрос в пакете, мс; список id)."""
    params = {}
    if ef is not None:
        params["ef"] = ef
    if nprobe is not None:
        params["nprobe"] = nprobe
    search_params = {"metric_type": metric}
    if params:
        search_params["params"] = params
    t0 = time.perf_counter()
    results = c.search(collection_name=name, data=[q.tolist() for q in queries], limit=k,
                       output_fields=["id"], search_params=search_params, filter=expr)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    ids = [[hit["id"] for hit in hits] for hits in results]
    return elapsed_ms / len(queries), ids


def measure(c, name: str, queries: np.ndarray, metric: str, ef: int | None,
            truth: list[list[int]], runs: int, warmup: int, expr: str = "",
            nprobe: int | None = None):
    """warm-up + runs прогонов пакетами + замер задержки одиночного запроса.

    Возвращает словарь: batch_ms (мс/запрос при поиске пакетом), batch_sd, single_ms (задержка
    одного запроса при отдельном вызове), recall, recall_sd.
    """
    for _ in range(warmup):
        run_search(c, name, queries[:1], metric, ef, expr, nprobe)
    times, recalls = [], []
    for _ in range(runs):
        ms, ids = run_search(c, name, queries, metric, ef, expr, nprobe)
        times.append(ms)
        rec, _ = recall_at_k(ids, truth)
        recalls.append(rec)
    return {
        "batch_ms": round(float(np.mean(times)), 2),
        "batch_sd": round(float(np.std(times)), 2),
        "single_ms": measure_single(c, name, queries, metric, ef, nprobe, expr),
        "recall": round(float(np.mean(recalls)), 3),
        "recall_sd": round(float(np.std(recalls)), 3),
    }


def recall_at_k(approx: list[list[int]], truth: list[list[int]], k: int = K):
    values = [len(set(a[:k]) & set(t[:k])) / k for a, t in zip(approx, truth)]
    return float(np.mean(values)), float(np.std(values))


def fmt(value, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}"

def index_names(c, name: str) -> list[str]:
    """Имена индексов коллекции (устойчиво к формату ответа SDK)."""
    names = []
    for item in c.list_indexes(collection_name=name):
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            value = item.get("index_name") or item.get("field_name")
            if value:
                names.append(value)
    return names


def variant(c, name: str, index_type: str, metric: str, params: dict | None = None):
    """Построить индекс и загрузить коллекцию, замерив: (построение, с; загрузка, с; память, МБ)."""
    build_s = build_index(c, name, index_type, metric, params)
    load_s, mem = load_index(c, name)
    return build_s, load_s, mem


def topk_identity(first: list[list[int]], second: list[list[int]], k: int = K) -> bool:
    return all(set(a[:k]) == set(b[:k]) for a, b in zip(first, second))


def make_structured(rng: np.random.Generator, n: int, intrinsic: int, clusters: int):
    """Структурированные векторы, близкие по свойствам к эмбеддингам.

    Чисто случайные векторы в 768 измерениях — патологический случай для ANN: расстояния
    концентрируются, и приближённый поиск теряет точность из-за геометрии данных, а не из-за индекса.
    Реальные эмбеддинги лежат на многообразии низкой размерности, поэтому данные генерируются как
    линейная проекция скрытого пространства размерности intrinsic (по умолчанию 32) с кластерной
    структурой (clusters центров) — как у тематически близких текстов.
    """
    projection = rng.normal(size=(DIM, intrinsic)).astype("float32")
    centers = rng.normal(size=(clusters, intrinsic)).astype("float32")
    hidden = (centers[rng.integers(0, clusters, size=n)]
              + 0.35 * rng.normal(size=(n, intrinsic)).astype("float32"))
    vectors = hidden @ projection.T
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors, centers


def make_queries(rng: np.random.Generator, count: int, centers: np.ndarray,
                 intrinsic: int) -> np.ndarray:
    """Запросы из тех же кластеров, что и данные (чтобы соседи реально существовали)."""
    projection = rng.normal(size=(DIM, intrinsic)).astype("float32")
    hidden = (centers[rng.integers(0, len(centers), size=count)]
              + 0.35 * rng.normal(size=(count, intrinsic)).astype("float32"))
    vectors = hidden @ projection.T
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors


def measure_single(c, name: str, queries: np.ndarray, metric: str,
                   ef: int | None, nprobe: int | None, expr: str = "", k: int = K) -> float:
    """Средняя задержка ОДНОГО запроса (каждый запрос — отдельный вызов search)."""
    times = []
    for query in queries:
        search_params = {"metric_type": metric}
        params = {}
        if ef is not None:
            params["ef"] = ef
        if nprobe is not None:
            params["nprobe"] = nprobe
        if params:
            search_params["params"] = params
        t0 = time.perf_counter()
        c.search(collection_name=name, data=[query.tolist()], limit=k,
                 output_fields=["id"], search_params=search_params, filter=expr)
        times.append((time.perf_counter() - t0) * 1000.0)
    return round(float(np.mean(times)), 2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Замеры для таблиц 3.1-3.6 (раздел 3.6)")
    parser.add_argument("--n", type=int, default=50000, help="число векторов в коллекции")
    parser.add_argument("--queries", type=int, default=100, help="запросов в одном прогоне")
    parser.add_argument("--runs", type=int, default=5, help="число прогонов (повторов)")
    parser.add_argument("--warmup", type=int, default=20, help="warm-up запросов до замеров")
    parser.add_argument("--intrinsic", type=int, default=32,
                        help="внутренняя размерность генерируемых векторов (структура данных)")
    parser.add_argument("--clusters", type=int, default=100, help="число кластеров в данных")
    parser.add_argument("--keep", action="store_true", help="не удалять коллекции после прогона")
    args = parser.parse_args()

    start_log(__file__)
    c = client()
    rng = np.random.default_rng(42)

    base, centers = make_structured(rng, args.n, args.intrinsic, args.clusters)
    queries = make_queries(rng, args.queries, centers, args.intrinsic)

    data_name, unnorm_name = "bench_data", "bench_unnorm"
    drop_if_exists(c, data_name)
    drop_if_exists(c, unnorm_name)

    print(f"=== Условия: N={args.n}, dim={DIM}, скрытая размерность={args.intrinsic}, "
          f"кластеров={args.clusters}, запросов={args.queries}, прогонов={args.runs}, "
          f"warm-up={args.warmup} ===")
    print(f"сервер Milvus: {c.get_server_version()}| контейнер: {MILVUS_CONTAINER}")
    print(f"норма векторов данных: {float(np.linalg.norm(base[0])):.6f} (единичная)")

    make_schema(c, data_name)
    insert_s = insert_all(c, data_name, build_rows(base, rng))
    print(f"вставка {args.n} векторов: {insert_s} с")

    # --- эталон (ground truth): точный поиск FLAT + COSINE ---
    set_index(c, data_name, "FLAT", "COSINE")
    _, truth_ids = run_search(c, data_name, queries, "COSINE")
    filters = {
        "без фильтра": "",
        "фильтр по operation_type": 'operation_type == "purchase"',
        "фильтр по mcc": 'mcc == "4900"',
        "фильтр по amount_minor > 1 000 000": "amount_minor > 1000000",
        "комбинированный фильтр": ('operation_type == "purchase" and mcc == "4900" '
                                   "and amount_minor > 1000000"),
    }
    truth_by_filter = {"без фильтра": truth_ids}
    for label, expr in filters.items():
        if expr:
            _, ids = run_search(c, data_name, queries, "COSINE", expr=expr)
            truth_by_filter[label] = ids
    print("эталон (FLAT/COSINE) рассчитан для 5 наборов запросов")

    result: dict = {"config": vars(args) | {"dim": DIM, "k": K, "server": c.get_server_version()},
                    "insert_seconds": insert_s}

    # --- Таблица 3.1: влияние efConstruction (HNSW, ef=64) ---
    print("\n=== Таблица 3.1 — влияние efConstruction (HNSW, ef=64) ===")
    print("efConstruction\tПостроение, с\tПоиск пакетом, мс/запрос\tЗадержка 1 запроса, мс\tRecall@10")
    t31 = []
    for ef_c in (50, 100, 400, 200):      # 200 — последним: на нём далее снимаем ef и фильтры
        build_s, load_s, _ = variant(c, data_name, "HNSW", "COSINE",
                                     {"M": 16, "efConstruction": ef_c})
        m = measure(c, data_name, queries, "COSINE", 64, truth_ids, args.runs, args.warmup)
        print(f"{ef_c}\t{build_s}\t{m['batch_ms']} ± {m['batch_sd']}\t{m['single_ms']}\t"
              f"{m['recall']} ± {m['recall_sd']}")
        t31.append({"efConstruction": ef_c, "build_s": build_s, "load_s": load_s, **m})
    result["t31_efConstruction"] = sorted(t31, key=lambda r: r["efConstruction"])

    # --- Таблица 3.2: влияние ef (HNSW efConstruction=200) ---
    print("\n=== Таблица 3.2 — влияние ef (HNSW efConstruction=200) ===")
    print("ef\tПоиск пакетом, мс/запрос\tЗадержка 1 запроса, мс\tRecall@10")
    t32 = []
    for ef in (16, 32, 64, 128, 256):
        m = measure(c, data_name, queries, "COSINE", ef, truth_ids, args.runs, args.warmup)
        print(f"{ef}\t{m['batch_ms']} ± {m['batch_sd']}\t{m['single_ms']}\t"
              f"{m['recall']} ± {m['recall_sd']}")
        t32.append({"ef": ef, **m})
    result["t32_ef"] = t32

    # --- Таблица 3.4: влияние фильтрации (HNSW M=16, efConstruction=200, ef=64) ---
    print("\n=== Таблица 3.4 — влияние фильтрации (HNSW, ef=64) ===")
    print("Тип запроса\tПоиск пакетом, мс/запрос\tЗадержка 1 запроса, мс\tRecall@10")
    t34 = []
    for label, expr in filters.items():
        m = measure(c, data_name, queries, "COSINE", 64, truth_by_filter[label],
                    args.runs, args.warmup, expr)
        print(f"{label}\t{m['batch_ms']} ± {m['batch_sd']}\t{m['single_ms']}\t"
              f"{m['recall']} ± {m['recall_sd']}")
        t34.append({"filter": label, "expr": expr, **m})
    result["t34_filters"] = t34



# --- Таблица 3.3: сравнение индексов ---
    print("\n=== Таблица 3.3 — сравнение индексов (N=%d, dim=%d, COSINE) ===" % (args.n, DIM))
    print("Индекс\tПостроение, с\tПоиск пакетом, мс/запрос\tЗадержка 1 запроса, мс\tRecall@10\tПамять, МБ")
    t33 = []
    index_variants = [
        ("FLAT", "FLAT", None),
        ("IVF_FLAT (nlist=224, nprobe=16)", "IVF_FLAT", {"nlist": 224}),
        ("HNSW (M=16, efC=200, ef=64)", "HNSW", {"M": 16, "efConstruction": 200}),
        ("IVF_SQ8 (nlist=224, nprobe=16)", "IVF_SQ8", {"nlist": 224}),
    ]
    for label, index_type, params in index_variants:
        build_s, load_s, mem = variant(c, data_name, index_type, "COSINE", params)
        ef = 64 if index_type == "HNSW" else None
        nprobe = 16 if index_type.startswith("IVF") else None
        m = measure(c, data_name, queries, "COSINE", ef, truth_ids,
                    args.runs, args.warmup, nprobe=nprobe)
        print(f"{label}\t{build_s}\t{m['batch_ms']} ± {m['batch_sd']}\t{m['single_ms']}\t"
              f"{m['recall']} ± {m['recall_sd']}\t{fmt(mem)}")
        t33.append({"index": label, "index_type": index_type, "build_s": build_s,
                    "load_s": load_s, "memory_mb": mem, "nprobe": nprobe, **m})
    result["t33_indexes"] = t33

    # --- Таблица 3.5: сравнение метрик на нормированных векторах ---
    print("\n=== Таблица 3.5 — сравнение метрик (нормированные векторы, HNSW-эталон COSINE) ===")
    print("Метрика\tRecall@10\tСовпадает с COSINE (top-10)\tПоиск пакетом, мс/запрос\tЗадержка 1 запроса, мс")
    t35 = []
    for metric in ("L2", "IP", "COSINE"):
        build_s, load_s, _ = variant(c, data_name, "FLAT", metric)
        m = measure(c, data_name, queries, metric, None, truth_ids, args.runs, args.warmup)
        _, ids = run_search(c, data_name, queries, metric)
        same = topk_identity(ids, truth_ids)
        print(f"{metric}\t{m['recall']} ± {m['recall_sd']}\t{same}\t"
              f"{m['batch_ms']} ± {m['batch_sd']}\t{m['single_ms']}")
        t35.append({"metric": metric, "same_topk_as_cosine": same, **m})
    result["t35_metrics_normalized"] = t35

    # --- 3.6.6, часть 2: НЕнормированные векторы (там метрики расходятся) ---
    n_small = min(args.n, 5000)
    raw, _ = make_structured(rng, n_small, args.intrinsic, args.clusters)
    raw = raw * rng.uniform(0.5, 2.0, size=(n_small, 1)).astype("float32")   # разные длины
    make_schema(c, unnorm_name)
    insert_all(c, unnorm_name, build_rows(raw, rng))
    print("\n=== 3.6.6, часть 2 — НЕнормированные векторы (N=%d) ===" % n_small)
    set_index(c, unnorm_name, "FLAT", "L2")
    _, raw_l2_ids = run_search(c, unnorm_name, queries, "L2")
    set_index(c, unnorm_name, "FLAT", "COSINE")
    _, raw_cos_ids = run_search(c, unnorm_name, queries, "COSINE")
    rec_cos_vs_l2, _ = recall_at_k(raw_cos_ids, raw_l2_ids)
    print("Метрика\tRecall@10 относительно L2\tСовпадает с L2 (top-10)")
    print(f"COSINE\t{rec_cos_vs_l2:.3f}\t{topk_identity(raw_cos_ids, raw_l2_ids)}")
    result["metrics_unnormalized"] = {
        "n": n_small,
        "cosine_recall_vs_l2_truth": round(rec_cos_vs_l2, 3),
        "same_topk": topk_identity(raw_cos_ids, raw_l2_ids),
    }

    if not args.keep:
        drop_if_exists(c, data_name)
        drop_if_exists(c, unnorm_name)
        print("\nколлекции bench_data / bench_unnorm удалены")

    out = Path(__file__).with_name("benchmark_result.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"результаты записаны: {out}")
    print("\n=== Сводка для отчёта ===")
    for row in result["t31_efConstruction"]:
        print(f"3.1 efConstruction={row['efConstruction']}: построение {row['build_s']} с, "
              f"поиск пакетом {row['batch_ms']}±{row['batch_sd']} мс/запрос, "
              f"задержка {row['single_ms']} мс, Recall@10 {row['recall']}")
    for row in result["t32_ef"]:
        print(f"3.2 ef={row['ef']}: поиск пакетом {row['batch_ms']}±{row['batch_sd']} мс/запрос, "
              f"задержка {row['single_ms']} мс, Recall@10 {row['recall']}")
    for row in result["t33_indexes"]:
        print(f"3.3 {row['index']}: построение {row['build_s']} с, поиск {row['batch_ms']} мс, "
              f"задержка {row['single_ms']} мс, Recall@10 {row['recall']}, "
              f"память {row['memory_mb']} МБ")
    for row in result["t34_filters"]:
        print(f"3.4 {row['filter']}: {row['batch_ms']}±{row['batch_sd']} мс/запрос, "
              f"задержка {row['single_ms']} мс, Recall {row['recall']}")
    for row in result["t35_metrics_normalized"]:
        print(f"3.5 {row['metric']}: Recall {row['recall']}, совпадение с COSINE={row['same_topk_as_cosine']}")
    print(f"3.6.6 (не нормировано): Recall(COSINE vs L2) = {rec_cos_vs_l2:.3f}, "
          f"совпадение={topk_identity(raw_cos_ids, raw_l2_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
