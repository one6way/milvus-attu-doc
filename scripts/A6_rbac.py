# -*- coding: utf-8 -*-
"""А.6. Настройка RBAC и ресурсных групп (по отчёту, разделы 2.7, 2.8, 3.5).

Создаёт:
  роли:   analyst, viewer            (admin — встроенная, не создаётся)
  юзеров: admin_user, analyst_user, viewer_user
  права:  analyst  -> Transactions(S+I+U+D+Search+Query), BankingProducts(Search+Query)
          viewer   -> BankingProducts(Search+Query)
  группы: rg_high_priority (админы+аналитики), rg_low_priority (наблюдатели)

Запуск:
  set MILVUS_HOST=127.0.0.1 & set MILVUS_PORT=19530
  set MILVUS_USER=root & set MILVUS_PASSWORD=MilvusDemo123
  python listings_script/A6_rbac.py
"""
from __future__ import annotations

import os
import sys

from pymilvus import MilvusClient

URI = os.environ.get("MILVUS_URI", "http://%s:%s" % (
    os.environ.get("MILVUS_HOST", "127.0.0.1"), os.environ.get("MILVUS_PORT", "19530")))
ROOT_USER = os.environ.get("MILVUS_USER", "root")
ROOT_PASSWORD = os.environ.get("MILVUS_PASSWORD", "MilvusDemo123")

COLL_PRODUCTS = "BankingProducts"
COLL_TX = "Transactions"

# Роли и права
ROLE_SPEC = {
    "analyst": {
        COLL_TX: ["Search", "Query", "Insert", "Delete", "Upsert"],
        COLL_PRODUCTS: ["Search", "Query"],
    },
    "viewer": {
        COLL_PRODUCTS: ["Search", "Query"],
    },
}
# Пользователи отчёта: имя -> (пароль, роль)
USER_SPEC = {
    "admin_user": ("AdminPass123!", "admin"),
    "analyst_user": ("AnalystPass123!", "analyst"),
    "viewer_user": ("ViewerPass123!", "viewer"),
}
# Ресурсные группы и привязка к коллекциям
RESOURCE_GROUPS = ["rg_high_priority", "rg_low_priority"]
COLLECTION_RG = {
    COLL_TX: "rg_high_priority",
    COLL_PRODUCTS: "rg_low_priority",
}


def admin():
    return MilvusClient(uri=URI, token=f"{ROOT_USER}:{ROOT_PASSWORD}")


def ensure_role(c, name):
    existing = [r for r in c.list_roles() if r == name]
    if existing:
        print(f"[skip] роль {name} уже существует")
        return False
    c.create_role(role_name=name)
    print(f"[create] роль {name}")
    return True


def ensure_user(c, name, password):
    if name in list(c.list_users()):
        print(f"[skip] пользователь {name} уже существует")
        return False
    c.create_user(user_name=name, password=password)
    print(f"[create] пользователь {name}")
    return True


def main() -> int:
    c = admin()

    # ---------- 1. Роли ----------
    print("== Роли ==")
    print("встроенные:", c.list_roles())
    for role in ROLE_SPEC:
        ensure_role(c, role)

    # ---------- 2. Права ----------
    print("== Права ==")
    for role, colls in ROLE_SPEC.items():
        for coll, privs in colls.items():
            for priv in privs:
                try:
                    c.grant_privilege_v2(role_name=role, privilege=priv, collection_name=coll)
                    print(f"  grant {role:<8} {priv:<8} on {coll}")
                except Exception as e:
                    print(f"  [warn] {role}/{priv}/{coll}: {e}")

    # ---------- 3. Пользователи и роли ----------
    print("== Пользователи ==")
    for user, (pwd, role) in USER_SPEC.items():
        ensure_user(c, user, pwd)
        try:
            c.grant_role(user_name=user, role_name=role)
            print(f"  grant_role {user} -> {role}")
        except Exception as e:
            print(f"  [warn] grant_role {user}: {e}")

    # ---------- 4. Ресурсные группы ----------
    print("== Ресурсные группы ==")
    existing_rg = c.list_resource_groups()
    print("существующие:", existing_rg)
    for rg in RESOURCE_GROUPS:
        if rg in existing_rg:
            print(f"[skip] {rg} уже существует")
            continue
        try:
            c.create_resource_group(name=rg)
            print(f"[create] resource group {rg}")
        except Exception as e:
            print(f"  [warn] {rg}: {e}")
    for coll, rg in COLLECTION_RG.items():
        try:
            c.alter_collection_properties(collection_name=coll,
                                          properties={"collection.resource_groups": rg})
            print(f"  bind {coll} -> {rg}")
        except Exception as e:
            print(f"  [warn] bind {coll}: {e}")

    # ---------- 5. Итог ----------
    print("== Итог ==")
    print("роли:        ", c.list_roles())
    print("пользователи:", list(c.list_users()))
    try:
        d = c.describe_role(role_name="analyst")
        print("analyst priv:", str(d)[:300])
    except Exception as e:
        print("describe_role(analyst):", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())