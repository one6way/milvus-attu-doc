# -*- coding: utf-8 -*-
"""Шаг отчёта §3.4.1: семантический поиск продуктов.

Эмбеддинги считает модель text-embedding-nomic-embed-text-v1.5 в LM Studio
(OpenAI-совместимый эндпоинт) — та же модель, которой загружена коллекция.

Запуск:  .venv\\Scripts\\python.exe scripts\\steps\\S09_search_products.py
"""
import json
import os
import urllib.request

from pymilvus import MilvusClient

# Провайдер эмбеддингов: LM Studio по умолчанию, переопределяется EMBED_API/EMBED_KEY.
API = os.environ.get("EMBED_API", "http://127.0.0.1:1234/v1/embeddings")
KEY = os.environ.get("EMBED_KEY", "sk-lm-local")
MODEL = "text-embedding-nomic-embed-text-v1.5"
URI, TOKEN = "http://127.0.0.1:19530", os.environ.get("MILVUS_TOKEN", "root:MilvusDemo123")

c = MilvusClient(uri=URI, token=TOKEN)


def embed(text, prefix="search_query: "):
    body = json.dumps({"model": MODEL, "input": [prefix + text]}).encode()
    req = urllib.request.Request(API, data=body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + KEY})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["data"][0]["embedding"]


print(f"модель эмбеддингов: {MODEL} (LM Studio, {API})")
print(f"размерность вектора: {len(embed('проверка'))}\n")

QUERIES = [
    "Выгодный вклад с высокой ставкой и возможностью снятия",
    "Кредит наличными без залога на длительный срок",
    "Дебетовая карта с кэшбэком и бесплатным обслуживанием",
]

for q in QUERIES:
    hits = c.search("BankingProducts", data=[embed(q)], anns_field="description_vector",
                    limit=3, output_fields=["product_name", "product_type", "interest_rate"])[0]
    print(f"ЗАПРОС: {q}")
    for i, h in enumerate(hits, 1):
        e = h["entity"]
        rate = f", ставка {e['interest_rate']:.1f}%" if e.get("interest_rate") is not None else ""
        print(f"  {i}. cos={h['distance']:.4f}  {e['product_type']:<8} {e['product_name']}{rate}")
    print()

print("Поиск с фильтром: product_type == 'deposit' and interest_rate > 7.5")
hits = c.search("BankingProducts", data=[embed("вклад с максимальной доходностью")],
                anns_field="description_vector", limit=3,
                filter="product_type == 'deposit' and interest_rate > 7.5",
                output_fields=["product_name", "interest_rate"])[0]
for i, h in enumerate(hits, 1):
    print(f"  {i}. cos={h['distance']:.4f}  {h['entity']['product_name']} "
          f"(ставка {h['entity']['interest_rate']:.1f}%)")
