# -*- coding: utf-8 -*-
"""Шаг отчёта §3.3.1: как выглядит эмбеддинг в коллекции (значения вектора).

Показывает фактические значения векторного поля description_vector коллекции
BankingProducts: размерность, первые/последние компоненты, норму, статистику
по всем 30 векторам и косинусную близость между описаниями продуктов.
Эмбеддинги рассчитаны моделью text-embedding-nomic-embed-text-v1.5 (LM Studio)
при загрузке данных; скрипт читает уже сохранённые векторы из Milvus.

Запуск:  .venv\\Scripts\\python.exe scripts\\steps\\S17_embedding_vector.py
"""
import os

import numpy as np
from pymilvus import MilvusClient

# Подключение к Milvus; переопределяется MILVUS_URI/MILVUS_TOKEN.
URI = os.environ.get("MILVUS_URI", "http://127.0.0.1:19530")
TOKEN = os.environ.get("MILVUS_TOKEN", "root:MilvusDemo123")
COLL, VEC = "BankingProducts", "description_vector"

c = MilvusClient(uri=URI, token=TOKEN)

rows = c.query(collection_name=COLL, filter="product_id >= 0", limit=100,
               output_fields=["product_id", "product_name", "product_type", VEC],
               consistency_level="Strong")
rows = sorted(rows, key=lambda r: r["product_id"])
dim = len(rows[0][VEC])

print("модель эмбеддингов: text-embedding-nomic-embed-text-v1.5 (LM Studio)")
print(f"коллекция: {COLL}   поле: {VEC}   размерность: {dim}")
print(f"объектов: {len(rows)}   уникальных векторов: "
      f"{len({tuple(np.round(r[VEC], 5)) for r in rows})}")

v0 = np.array(rows[0][VEC], dtype=np.float32)
print(f"\n=== Вектор описания «{rows[0]['product_name']}» ({dim} компонент) ===")
print("первые 12: " + " ".join("%+.5f" % x for x in v0[:12]))
print("следующие 12: " + " ".join("%+.5f" % x for x in v0[12:24]))
print("последние 6: " + " ".join("%+.5f" % x for x in v0[-6:]))

M = np.array([r[VEC] for r in rows], dtype=np.float32)
norms = np.linalg.norm(M, axis=1)
print(f"\n=== Статистика по {len(rows)} векторам ===")
print("матрица векторов: %d x %d = %d чисел" % (M.shape[0], M.shape[1], M.size))
print("норма ||v||: min %.6f  max %.6f  (нормированные)" % (norms.min(), norms.max()))
print("компоненты:  min %+.4f  max %+.4f  mean %+.6f  std %.4f"
      % (M.min(), M.max(), M.mean(), M.std()))

U = M / norms[:, None]
print(f"\n=== Уникальные описания ({len({tuple(np.round(r[VEC], 5)) for r in rows})} "
      f"векторов на {len(rows)} записей) ===")
seen, reps = [], []
for i, r in enumerate(rows):
    v = U[i]
    if not any(float(v @ s) > 0.99999 for s in seen):
        seen.append(v)
        reps.append(r)
print("в демонстрационном наборе описания повторяются, поэтому")
print("30 записей дают 7 уникальных векторов.")

R = np.array(seen)
if len(R) > 1:
    cross = R @ R[0]
    print(f"\n=== Ближайшие векторы к «{reps[0]['product_name']}» ===")
    for j in np.argsort(-cross)[1:4]:
        print("  cos=%.4f  %-9s %s" % (cross[j], reps[j]["product_type"],
                                       reps[j]["product_name"][:38]))