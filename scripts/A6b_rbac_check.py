# -*- coding: utf-8 -*-
"""А.6/3.5.2. Проверка разграничения доступа реальными данными.

Подключается под каждым пользователем отчёта и выполняет разрешённые/запрещённые
операции. Печатает таблицу: пользователь | коллекция | операция | результат.

Запуск:  python listings_script/A6b_rbac_check.py
"""
from __future__ import annotations

import os
import sys

from pymilvus import MilvusClient

URI = os.environ.get("MILVUS_URI", "http://%s:%s" % (
    os.environ.get("MILVUS_HOST", "127.0.0.1"), os.environ.get("MILVUS_PORT", "19530")))

USERS = {
    "admin_user": "AdminPass123!",
    "analyst_user": "AnalystPass123!",
    "viewer_user": "ViewerPass123!",
}

CASES = [
    # (пользователь, коллекция, операция, ожидание)
    ("viewer_user", "BankingProducts", "search", "ALLOW"),
    ("viewer_user", "Transactions", "search", "DENY"),
    ("viewer_user", "Transactions", "insert", "DENY"),
    ("analyst_user", "BankingProducts", "search", "ALLOW"),
    ("analyst_user", "Transactions", "search", "ALLOW"),
    ("analyst_user", "Transactions", "insert", "ALLOW"),
    ("analyst_user", "Transactions", "create_collection", "DENY"),
]


def client(user, pwd):
    return MilvusClient(uri=URI, token=f"{user}:{pwd}")


def run(c, coll, op):
    try:
        if op == "search":
            c.search(coll, data=[[0.0] * 768], anns_field=("description_vector" if coll == "BankingProducts" else "purpose_vector"),
                     limit=1)
        elif op == "insert":
            c.insert(coll, [{"account_id": 1, "card_id": 1, "transaction_date": "2025-01-01T00:00:00",
                             "amount_minor": 1, "currency_code": "RUB", "operation_type": "credit",
                             "purpose": "probe", "mcc": "0000", "purpose_vector": [0.0] * 768}])
        elif op == "create_collection":
            c.create_collection("probe_rbac_tmp")
            c.drop_collection("probe_rbac_tmp")
        return True
    except Exception:
        return False


def main() -> int:
    rows = []
    for user, coll, op, expect in CASES:
        c = client(user, USERS[user])
        allowed = run(c, coll, op)
        got = "ALLOW" if allowed else "DENY"
        ok = "OK" if got == expect else "!!"
        rows.append((user, coll, op, got, expect, ok))
        print(f"{user:<14} {coll:<16} {op:<18} got={got:<5} expect={expect:<5} {ok}")

    print("\nИТОГ:", "все проверки совпали" if all(r[5] == "OK" for r in rows) else "есть расхождения")
    return 0


if __name__ == "__main__":
    sys.exit(main())