"""Проверка кода отчёта по разделам 2.7, 2.8, 3.5 (RBAC и ресурсные группы).

Прогон на живом Milvus. Фиксируем: какие вызовы из отчёта существуют, какие
падают, и как та же задача решается на актуальном API.

Запуск:  python .\\verify\\probe_rbac.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    ROOT_PASSWORD,
    ROOT_USER,
    URI,
    DataType,
    client,
    drop_if_exists,
    probe,
    report_vector,
    start_log,
    summary,
)

COLL = "probe_rb_products"
TX = "probe_rb_tx"

PRIVS_FROM_REPORT = [
    "Search", "Query", "Insert", "Delete", "Upsert",
    "CreateIndex", "DropIndex", "Load", "Release",
]


def restore_default_rg(c) -> None:
    """Возвращает query-узлы в __default_resource_group и убирает свои RG.

    Нюанс: чтобы отдать узел обратно, нужно requests=0 И limits=0 у группы
    (иначе Milvus отвечает "requests or limits is required").
    """
    from pymilvus.client.types import ResourceGroupConfig

    for rg in ("rg_low_priority", "rg_probe_demo", "rg_high_priority"):
        try:
            c.update_resource_groups({
                rg: ResourceGroupConfig(
                    requests={"node_num": 0},
                    limits={"node_num": 0},
                    transfer_from=[{"resource_group": "__default_resource_group"}],
                    transfer_to=[{"resource_group": "__default_resource_group"}],
                )
            })
        except Exception:  # noqa: BLE001
            pass
        try:
            c.drop_resource_group(name=rg)
        except Exception:  # noqa: BLE001
            pass


def cleanup(c) -> None:
    try:
        for user in c.list_users():
            if user.startswith("probe_"):
                c.drop_user(user_name=user)
    except Exception:  # noqa: BLE001
        pass
    try:
        for role in c.list_roles():
            if not role.startswith("probe_"):
                continue
            revoke_all(c, role)
            try:
                c.drop_role(role_name=role)
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass
    restore_default_rg(c)
    drop_if_exists(c, COLL)
    drop_if_exists(c, TX)


def make_collections(c) -> None:
    drop_if_exists(c, COLL)
    s = c.create_schema(auto_id=True, enable_dynamic_field=False)
    s.add_field("product_id", DataType.INT64, is_primary=True)
    s.add_field("product_name", DataType.VARCHAR, max_length=150)
    s.add_field("product_type", DataType.VARCHAR, max_length=20)
    s.add_field("description_vector", DataType.FLOAT_VECTOR, dim=8)
    c.create_collection(collection_name=COLL, schema=s)
    ip = c.prepare_index_params()
    ip.add_index(field_name="description_vector", index_type="FLAT", metric_type="COSINE")
    c.create_index(collection_name=COLL, index_params=ip)
    c.insert(COLL, [{
        "product_name": "Вклад",
        "product_type": "deposit",
        "description_vector": report_vector(8, seed=1),
    }])
    c.flush(collection_name=COLL)
    c.load_collection(collection_name=COLL)

    drop_if_exists(c, TX)
    st = c.create_schema(auto_id=True, enable_dynamic_field=False)
    st.add_field("transaction_id", DataType.INT64, is_primary=True)
    st.add_field("purpose", DataType.VARCHAR, max_length=500)
    st.add_field("amount_minor", DataType.INT64)
    st.add_field("purpose_vector", DataType.FLOAT_VECTOR, dim=8)
    c.create_collection(collection_name=TX, schema=st)
    ip2 = c.prepare_index_params()
    ip2.add_index(field_name="purpose_vector", index_type="FLAT", metric_type="COSINE")
    c.create_index(collection_name=TX, index_params=ip2)
    c.load_collection(collection_name=TX)

def revoke_all(c, role: str) -> None:
    """Снять все права роли (иначе Milvus не даёт её удалить).

    describe_role() в pymilvus 3.0.2 может вернуть пустой список privileges,
    поэтому снимаем по известному набору привилегий и коллекций.
    """
    privs = ["Search", "Query", "Insert", "Delete", "Upsert",
             "CreateIndex", "DropIndex", "Load", "Release",
             "CreateCollection", "DropCollection"]
    for coll in (COLL, TX):
        for priv in privs:
            try:
                c.revoke_privilege_v2(role_name=role, privilege=priv, collection_name=coll)
            except Exception:  # noqa: BLE001
                pass


def demo_transfer(c) -> None:
    """Демонстрация 3.5.3: перенос узла опустошает __default_resource_group."""
    from pymilvus.client.types import ResourceGroupConfig

    before = c.describe_resource_group(name="__default_resource_group").num_available_node
    print(f"\n--- 3.5.3 перенос query-узла: узлов в __default_resource_group ДО = {before} ---")
    with probe("3.5.3 создать rg_probe_demo и перенести 1 узел из __default_resource_group"):
        c.create_resource_group(name="rg_probe_demo")
        c.update_resource_groups({
            "rg_probe_demo": ResourceGroupConfig(
                requests={"node_num": 1},
                limits={"node_num": 1},
                transfer_from=[{"resource_group": "__default_resource_group"}],
                transfer_to=[{"resource_group": "__default_resource_group"}],
            )
        })
        after = c.describe_resource_group(name="__default_resource_group").num_available_node
        print(f"  узлов в __default_resource_group ПОСЛЕ = {after}")

    with probe("Последствие: load_collection при пустой __default_resource_group", expect_fail=True):
        c.load_collection(collection_name=COLL)

    with probe("Откат: вернуть узел (requests=0, limits=0) и удалить группу"):
        c.update_resource_groups({
            "rg_probe_demo": ResourceGroupConfig(
                requests={"node_num": 0},
                limits={"node_num": 0},
                transfer_from=[{"resource_group": "__default_resource_group"}],
                transfer_to=[{"resource_group": "__default_resource_group"}],
            )
        })
        c.drop_resource_group(name="rg_probe_demo")
        print(f"  узлов в __default_resource_group после отката = "
              f"{c.describe_resource_group(name='__default_resource_group').num_available_node}")


def main() -> int:
    start_log(__file__)
    c = client()
    cleanup(c)
    make_collections(c)

    # ---------- 3.5.1 create_role('admin') ----------
    with probe("3.5.1 create_role('admin') — роль admin встроенная (ожидаем ошибку)", expect_fail=True):
        c.create_role(role_name="admin")

    # ---------- grant_privilege_v2 на встроенную роль admin ----------
    with probe("3.5.1 grant_privilege_v2(role_name='admin') — выдача прав встроенной роли admin"):
        c.grant_privilege_v2(role_name="admin", privilege="Search", collection_name=COLL)
        print("  права встроенной роли admin выдаются (роль создать нельзя, а права — можно)")

    # ---------- Какие привилегии из списка отчёта реально существуют ----------
    with probe("3.5.1 перебор привилегий из отчёта (роль probe_analyst)"):
        c.create_role(role_name="probe_analyst")
        for priv in PRIVS_FROM_REPORT:
            try:
                c.grant_privilege_v2(role_name="probe_analyst", privilege=priv, collection_name=COLL)
                print(f"  [OK]      {priv}")
            except Exception as exc:  # noqa: BLE001
                msg = f"{type(exc).__name__}: {exc}".replace("\n", " ")[:150]
                print(f"  [ОШИБКА]  {priv} -> {msg}")
        revoke_all(c, "probe_analyst")
        c.drop_role(role_name="probe_analyst")

    # ---------- Роли и пользователи как в отчёте ----------
    with probe("3.5.1 create_role(analyst/viewer) + create_user + grant_role"):
        c.create_role(role_name="probe_analyst")
        c.create_role(role_name="probe_viewer")
        for priv in ("Search", "Query"):
            c.grant_privilege_v2(role_name="probe_analyst", privilege=priv, collection_name=COLL)
        for priv in ("Search", "Query", "Insert", "Delete"):
            c.grant_privilege_v2(role_name="probe_analyst", privilege=priv, collection_name=TX)
        for priv in ("Search", "Query"):
            c.grant_privilege_v2(role_name="probe_viewer", privilege=priv, collection_name=COLL)
        c.create_user(user_name="probe_analyst_user", password="AnalystPass123!")
        c.create_user(user_name="probe_viewer_user", password="ViewerPass123!")
        c.grant_role(user_name="probe_analyst_user", role_name="probe_analyst")
        c.grant_role(user_name="probe_viewer_user", role_name="probe_viewer")

    # ---------- 3.5.2 Проверка разграничения доступа ----------
    print("\n--- 3.5.2 проверка доступа под каждым пользователем ---")

    def check(user: str, pwd: str, coll: str, op: str) -> str:
        try:
            cc = client(user=user, password=pwd)
            if op == "search":
                cc.search(collection_name=coll, data=[report_vector(8, seed=2)], limit=1)
            elif op == "insert":
                cc.insert(collection_name=coll, data=[{}])
            elif op == "create_collection":
                ss = cc.create_schema(auto_id=True, enable_dynamic_field=True)
                ss.add_field("id", DataType.INT64, is_primary=True)
                ss.add_field("v", DataType.FLOAT_VECTOR, dim=8)
                cc.create_collection(collection_name="probe_should_not_exist", schema=ss)
            return "OK"
        except Exception as exc:  # noqa: BLE001
            return f"DENIED ({type(exc).__name__}: {str(exc)[:90]})"

    cases = [
        ("probe_viewer_user", "ViewerPass123!", COLL, "search"),
        ("probe_viewer_user", "ViewerPass123!", TX, "search"),
        ("probe_viewer_user", "ViewerPass123!", TX, "insert"),
        ("probe_analyst_user", "AnalystPass123!", TX, "search"),
        ("probe_analyst_user", "AnalystPass123!", TX, "insert"),
        ("probe_analyst_user", "AnalystPass123!", COLL, "create_collection"),
    ]
    print(f"{'пользователь':<20} {'коллекция':<18} {'операция':<18} результат")
    for user, pwd, coll, op in cases:
        print(f"{user:<20} {coll:<18} {op:<18} {check(user, pwd, coll, op)}")

# ---------- 3.5.3 update_user(resource_groups=[...]) ----------
    with probe("3.5.3 update_user(user_name=..., resource_groups=[...]) как в отчёте (ожидаем ошибку)", expect_fail=True):
        c.update_user(user_name="probe_viewer_user", resource_groups=["rg_low_priority"])

    with probe("3.5.3 describe_user('probe_viewer_user') — что реально возвращает"):
        print(f"  {c.describe_user(user_name='probe_viewer_user')}")

    # ---------- 3.5.3 create_resource_group ----------
    with probe("3.5.3 create_resource_group('rg_low_priority')"):
        c.create_resource_group(name="rg_low_priority")
        print(f"  группы: {c.list_resource_groups()}")

    # ---------- 3.5.3 transfer_node ----------
    with probe("3.5.3 admin_client.transfer_node(...) — метод у MilvusClient (ожидаем ошибку)", expect_fail=True):
        c.transfer_node(source_group="__default_resource_group",
                        target_group="rg_low_priority", num_nodes=1)

    with probe("3.5.3 utility.transfer_node(...) на Standalone (ожидаем ошибку)", expect_fail=True):
        from pymilvus import utility

        utility.transfer_node("__default_resource_group", "rg_low_priority", 1)

    # ---------- Актуальный способ работы с ресурсными группами ----------
    with probe("Актуально: update_resource_groups(ResourceGroupConfig из pymilvus.client.types)"):
        from pymilvus.client.types import ResourceGroupConfig

        configs = {
            "rg_low_priority": ResourceGroupConfig(
                requests={"node_num": 1},
                limits={"node_num": 2},
                transfer_from=[{"resource_group": "__default_resource_group"}],
                transfer_to=[{"resource_group": "__default_resource_group"}],
            )
        }
        c.update_resource_groups(configs)
        print(f"  {c.describe_resource_group(name='rg_low_priority')}")

    with probe("Актуально: alter_collection_properties({'collection.resource_groups': ...})"):
        c.alter_collection_properties(
            collection_name=COLL,
            properties={"collection.resource_groups": "rg_low_priority"},
        )
        print("  RG привязана к КОЛЛЕКЦИИ (а не к пользователю, как в отчёте)")

    demo_transfer(c)

    cleanup(c)
    return summary()




if __name__ == "__main__":
    raise SystemExit(main())
