# -*- coding: utf-8 -*-
"""Шаг отчёта: схема коллекций и индексы (подтверждение §3.2.2–3.2.3).

Запуск:  .venv\\Scripts\\python.exe scripts\\steps\\S06_schema.py
"""
from pymilvus import MilvusClient

URI, TOKEN = "http://127.0.0.1:19530", "root:MilvusDemo123"
c = MilvusClient(uri=URI, token=TOKEN)

TYPE = {5: "INT64", 21: "VARCHAR", 10: "FLOAT", 4: "INT32", 101: "FLOAT_VECTOR"}

for coll in ["BankingProducts", "Transactions"]:
    d = c.describe_collection(coll)
    print(f"=== {coll} ===")
    for f in d["fields"]:
        t = TYPE.get(f["type"], f["type"])
        extra = ""
        if "max_length" in f.get("params", {}):
            extra = f"({f['params']['max_length']})"
        if "dim" in f.get("params", {}):
            extra = f"(dim={f['params']['dim']})"
        flags = []
        if f.get("is_primary"):
            flags.append("PK")
        if f.get("auto_id"):
            flags.append("auto")
        if f.get("nullable"):
            flags.append("nullable")
        print(f"  {f['name']:<20} {t}{extra:<14} {' '.join(flags)}")
    idx = c.list_indexes(coll)
    print("  индексы:", ", ".join(i if isinstance(i, str) else str(i) for i in idx))
    print()
