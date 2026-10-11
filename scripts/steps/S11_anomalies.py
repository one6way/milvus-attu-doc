# -*- coding: utf-8 -*-
"""Шаг отчёта §3.4.3: выявление аномалий — косинусное расстояние до центроида (θ = μ − 2σ).

Векторы уже в Milvus (text-embedding-nomic-embed-text-v1.5, LM Studio).
Для проверки «новых» назначений эмбеддинг считается тем же эндпоинтом.

Запуск:  .venv\\Scripts\\python.exe scripts\\steps\\S11_anomalies.py
"""
import json
import urllib.request

import numpy as np
from pymilvus import MilvusClient

API = "http://127.0.0.1:1234/v1/embeddings"
KEY = "sk-lm-STX4hpuF:WyBJuG9KKXe9MCMuTz6s"
MODEL = "text-embedding-nomic-embed-text-v1.5"
URI, TOKEN = "http://127.0.0.1:19530", "root:MilvusDemo123"

c = MilvusClient(uri=URI, token=TOKEN)


def embed(text, prefix="search_query: "):
    body = json.dumps({"model": MODEL, "input": [prefix + text]}).encode()
    req = urllib.request.Request(API, data=body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + KEY})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["data"][0]["embedding"]


rows = c.query("Transactions", filter="", output_fields=["purpose", "purpose_vector"], limit=100)
vecs = np.array([r["purpose_vector"] for r in rows], dtype=np.float32)
purposes = [r["purpose"] for r in rows]

centroid = vecs.mean(axis=0)
centroid /= np.linalg.norm(centroid)
sims = vecs @ centroid
mu, sigma = float(sims.mean()), float(sims.std())
theta = mu - 2 * sigma

print(f"модель эмбеддингов: {MODEL} (LM Studio)")
print(f"транзакций: {len(rows)}   центроид: shape={centroid.shape}   "
      f"||c||={np.linalg.norm(centroid):.6f}")
print(f"μ = {mu:.4f}   σ = {sigma:.4f}   θ = μ − 2σ = {theta:.4f}\n")
print(f"{'cos':>8}  {'метка':<11} назначение платежа")
for s, p in sorted(zip(sims, purposes)):
    print(f"{s:>8.4f}  {'АНОМАЛИЯ' if s < theta else '':<11} {p}")

NEW = [
    "Оплата продуктов в магазине у дома",
    "Покупка золотых слитков и валюты в обменнике",
    "Перевод средств в криптовалютный обменник без назначения",
]
below = 0
print("\nПроверка новых назначений (не из коллекции):")
for t in NEW:
    s = float(np.array(embed(t), dtype=np.float32) @ centroid)
    hit = s < theta
    below += hit
    print(f"{s:>8.4f}  {'АНОМАЛИЯ (ниже θ)' if hit else 'норма':<18} {t}")

print(f"\nИТОГ: аномалий ниже θ среди {len(rows)} транзакций — {int((sims < theta).sum())}; "
      f"среди {len(NEW)} новых назначений — {below}.")
print(f"      минимальное сходство в наборе: {sims.min():.4f} (θ = {theta:.4f})")
