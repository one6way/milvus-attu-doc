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
        d = None
    # describe_resource_group возвращает объект ResourceGroupInfo:
    # берём атрибуты (а не dict.get), иначе выводится «—»
    avail = getattr(d, "num_available_node", "—") if d is not None else "—"
    cap = getattr(d, "capacity", "—") if d is not None else "—"
    print(f"  {rg:<24} доступно узлов={avail}  ёмкость={cap}")

print("\nПривязка коллекций к группам (collection.resource_groups):")
for coll in ["Transactions", "BankingProducts"]:
    d = c.describe_collection(coll)
    props = d.get("properties", {}) or {}
    rg = props.get("collection.resource_groups", "—")
    print(f"  {coll:<18} -> {rg}")
