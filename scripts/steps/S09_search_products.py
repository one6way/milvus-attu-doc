# -*- coding: utf-8 -*-
"""Шаг отчёта §3.4.1: семантический поиск банковских продуктов (модель E5).

Запуск:  .venv\\Scripts\\python.exe report\\steps\\S09_search_products.py
"""
from sentence_transformers import SentenceTransformer
from pymilvus import MilvusClient

MODEL = "intfloat/multilingual-e5-base"
URI, TOKEN = "http://127.0.0.1:19530", "root:MilvusDemo123"

model = SentenceTransformer(MODEL)
c = MilvusClient(uri=URI, token=TOKEN)

QUERIES = [
    "Выгодный вклад с высокой ставкой и возможностью снятия",
    "Кредит наличными без залога на длительный срок",
    "Дебетовая карта с кэшбэком и бесплатным обслуживанием",
]

for q in QUERIES:
    vec = model.encode(["query: " + q], normalize_embeddings=True)[0].tolist()
    hits = c.search("BankingProducts", data=[vec], anns_field="description_vector",
                    limit=3, output_fields=["product_name", "product_type", "interest_rate"])[0]
    print(f"\nЗАПРОС: {q}")
    for i, h in enumerate(hits, 1):
        e = h["entity"]
        rate = f", ставка {e['interest_rate']:.1f}%" if e.get("interest_rate") is not None else ""
        print(f"  {i}. cos={h['distance']:.4f}  {e['product_type']:<8} {e['product_name']}{rate}")

print("\nПоиск с фильтром: product_type == 'deposit' and interest_rate > 7.5")
vec = model.encode(["query: вклад с максимальной доходностью"], normalize_embeddings=True)[0].tolist()
hits = c.search("BankingProducts", data=[vec], anns_field="description_vector", limit=3,
                filter="product_type == 'deposit' and interest_rate > 7.5",
                output_fields=["product_name", "interest_rate"])[0]
for i, h in enumerate(hits, 1):
    print(f"  {i}. cos={h['distance']:.4f}  {h['entity']['product_name']} (ставка {h['entity']['interest_rate']:.1f}%)")
