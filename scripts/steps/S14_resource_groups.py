# -*- coding: utf-8 -*-
"""Шаг отчёта §3.5.3: ресурсные группы и их привязка к коллекциям.

Запуск:  .venv\\Scripts\\python.exe scripts\\steps\\S14_resource_groups.py
"""
from pymilvus import MilvusClient

URI, TOKEN = "http://127.0.0.1:19530", "root:MilvusDemo123"
c = MilvusClient(uri=URI, token=TOKEN)

print("Ресурсные группы:")
for rg in c.list_resource_groups():
    try:
        d = c.describe_resource_group(name=rg)
    except Exception:
        d = {}
    nodes = d.get("num_nodes", d.get("nodes", "—")) if isinstance(d, dict) else "—"
    print(f"  {rg:<24} nodes={nodes}")

print("\nПривязка коллекций к группам (collection.resource_groups):")
for coll in ["Transactions", "BankingProducts"]:
    d = c.describe_collection(coll)
    props = d.get("properties", {}) or {}
    rg = props.get("collection.resource_groups", "—")
    print(f"  {coll:<18} -> {rg}")
