# -*- coding: utf-8 -*-
"""Шаг отчёта §3.4.2: категоризация транзакций — поиск похожих назначений платежей.

Запуск:  .venv\\Scripts\\python.exe report\\steps\\S10_categorization.py
"""
from sentence_transformers import SentenceTransformer
from pymilvus import MilvusClient

MODEL = "intfloat/multilingual-e5-base"
URI, TOKEN = "http://127.0.0.1:19530", "root:MilvusDemo123"

model = SentenceTransformer(MODEL)
c = MilvusClient(uri=URI, token=TOKEN)

QUERIES = [
    "Оплата продуктов в магазине",
    "Платёж за коммунальные услуги",
    "Перевод зарплаты сотруднику",
]

for q in QUERIES:
    vec = model.encode(["query: " + q], normalize_embeddings=True)[0].tolist()
    hits = c.search("Transactions", data=[vec], anns_field="purpose_vector", limit=3,
                    output_fields=["purpose", "operation_type", "mcc"])[0]
    print(f"\nЗАПРОС: {q}  ->  категория по MCC")
    for i, h in enumerate(hits, 1):
        e = h["entity"]
        print(f"  {i}. cos={h['distance']:.4f}  [{e['mcc'] or '—'}] {e['operation_type']:<9} {e['purpose']}")
