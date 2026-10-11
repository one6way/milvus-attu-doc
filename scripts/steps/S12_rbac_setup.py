# -*- coding: utf-8 -*-
"""Шаг отчёта §3.5.1: чистая настройка RBAC (роли, пользователи) + §3.5.3 (ресурсные группы).

Сначала удаляет прежние роли/пользователи отчёта, затем создаёт заново
(скрипт listings_script/A6_rbac.py), чтобы вывод был «с нуля».

Запуск:  .venv\\Scripts\\python.exe report\\steps\\S12_rbac_setup.py
"""
import importlib.util
import os
import sys

from pymilvus import MilvusClient

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
URI, TOKEN = "http://127.0.0.1:19530", "root:MilvusDemo123"
c = MilvusClient(uri=URI, token=TOKEN)

print("== очистка прежних сущностей ==")
for u in ["admin_user", "analyst_user", "viewer_user"]:
    if u in list(c.list_users()):
        c.drop_user(user_name=u)
        print(f"  drop user {u}")
for r in ["analyst", "viewer"]:
    if r in list(c.list_roles()):
        try:
            d = c.describe_role(role_name=r)
            for p in d.get("privileges", []):
                c.revoke_privilege_v2(role_name=r, privilege=p["privilege"],
                                      collection_name=p.get("object_name", "*"))
        except Exception as e:
            print(f"  [warn] revoke {r}: {e}")
        c.drop_role(role_name=r)
        print(f"  drop role {r}")
print()

# запуск штатного скрипта отчёта
spec = importlib.util.spec_from_file_location("a6", os.path.join(ROOT, "listings_script", "A6_rbac.py"))
a6 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a6)
sys.exit(a6.main())
