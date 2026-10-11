# -*- coding: utf-8 -*-
"""Шаг отчёта §3.4.2: категоризация транзакций — поиск похожих назначений платежей.

Модель эмбеддингов: text-embedding-nomic-embed-text-v1.5 (LM Studio).

Запуск:  .venv\\Scripts\\python.exe scripts\\steps\\S10_categorization.py
"""
import json
import urllib.request

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


print(f"модель эмбеддингов: {MODEL} (LM Studio)\n")

QUERIES = [
    "Оплата продуктов в магазине",
    "Платёж за коммунальные услуги",
    "Перевод зарплаты сотруднику",
]

for q in QUERIES:
    hits = c.search("Transactions", data=[embed(q)], anns_field="purpose_vector", limit=3,
                    output_fields=["purpose", "operation_type", "mcc"])[0]
    print(f"ЗАПРОС: {q}  ->  категория по MCC")
    for i, h in enumerate(hits, 1):
        e = h["entity"]
        print(f"  {i}. cos={h['distance']:.4f}  [{e['mcc'] or '—'}] "
              f"{e['operation_type']:<9} {e['purpose']}")
    print()
