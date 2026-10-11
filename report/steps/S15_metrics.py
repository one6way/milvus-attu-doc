# -*- coding: utf-8 -*-
"""Шаг отчёта §3.6: результаты экспериментов (по данным verify/benchmark_result.json).

Запуск:  .venv\\Scripts\\python.exe report\\steps\\S15_metrics.py
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "milvusattugorobec", "verify", "benchmark_result.json")
d = json.load(io.open(SRC, encoding="utf-8"))

cfg = d["config"]
print(f"Условия: Milvus {cfg['server']}, N={cfg['n']}, dim={cfg['dim']}, k={cfg['k']}, "
      f"запросов={cfg['queries']}, прогонов={cfg['runs']}")
print(f"Вставка {cfg['n']} векторов: {d['insert_seconds']} с\n")


def table(title, rows, cols, hdr=None):
    print(f"--- {title} ---")
    hdr = hdr or cols
    print("  " + "  ".join(f"{h:>12}" for h in hdr))
    for r in rows:
        print("  " + "  ".join(f"{str(r.get(c, '')):>12}" for c in cols))
    print()


table("Таблица 3.1 — влияние efConstruction", d["t31_efConstruction"],
      ["efConstruction", "build_s", "load_s", "batch_ms", "single_ms", "recall"],
      ["efC", "build_s", "load_s", "batch_ms", "single_ms", "Recall@10"])
table("Таблица 3.2 — влияние ef", d["t32_ef"],
      ["ef", "batch_ms", "single_ms", "recall"],
      ["ef", "batch_ms", "single_ms", "Recall@10"])
table("Таблица 3.3 — сравнение индексов", d["t33_indexes"],
      ["index", "build_s", "load_s", "memory_mb", "single_ms", "recall"],
      ["индекс", "build_s", "load_s", "mem_MB", "single_ms", "Recall@10"])
print("--- Таблица 3.4 — скалярные фильтры ---")
for r in d["t34_filters"]:
    print(f"  {r['filter']:<46} batch={r['batch_ms']:<6} single={r['single_ms']:<6} recall={r['recall']}")
print()
table("Таблица 3.5 — метрики на нормированных векторах", d["t35_metrics_normalized"],
      ["metric", "batch_ms", "single_ms", "recall"],
      ["метрика", "batch_ms", "single_ms", "Recall@10"])
mn = d["metrics_unnormalized"]
print(f"Ненормированные векторы (N={mn['n']}): cosine-recall против L2-эталона = "
      f"{mn['cosine_recall_vs_l2_truth']}, совпадение топ-k = {mn['same_topk']}")
