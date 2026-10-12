# -*- coding: utf-8 -*-
"""Шаг отчёта: количество загруженных строк по коллекциям (§3.3.3).

Запуск:  .venv\\Scripts\\python.exe scripts\\steps\\S08_counts.py
"""
from pymilvus import MilvusClient

URI, TOKEN = "http://127.0.0.1:19530", "root:MilvusDemo123"
c = MilvusClient(uri=URI, token=TOKEN)

COLLS = ["BankingProducts", "Transactions", "Currencies", "Clients", "Accounts", "Cards"]
print(f"{'коллекция':<20}{'строк':>7}{'статус':>12}")
for n in COLLS:
    cnt = c.query(n, filter="", output_fields=["count(*)"])[0]["count(*)"]
    state = c.get_load_state(n)["state"]
    print(f"{n:<20}{cnt:>7}{str(state).split('.')[-1]:>12}")
