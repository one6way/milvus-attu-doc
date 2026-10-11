"""Возврат query-узлов в __default_resource_group после экспериментов с RG.

Перенос узлов (как в разделе 3.5.3 отчёта) опустошает __default_resource_group
на Standalone, после чего load/search падают с
"resource group node not enough[rg=__default_resource_group][currentNodeNum=0]".

Скрипт пробует несколько способов отката и печатает, какой сработал.

Запуск:  python .\\verify\\restore_rg.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DataType, client, drop_if_exists, start_log  # noqa: E402

RG = "rg_low_priority"
DEFAULT_RG = "__default_resource_group"


def show(c, title: str) -> None:
    info = c.describe_resource_group(name=DEFAULT_RG)
    print(f"{title}: default capacity={info.capacity}, available={info.num_available_node}, groups={c.list_resource_groups()}")


def main() -> int:
    start_log(__file__)
    c = client()
    show(c, "ДО")

    from pymilvus.client.types import ResourceGroupConfig

    attempts = {
        "вариант 1: у rg limits=0, у default requests=1": {
            DEFAULT_RG: ResourceGroupConfig(
                requests={"node_num": 1},
                limits={"node_num": 5},
                transfer_from=[{"resource_group": RG}],
                transfer_to=[{"resource_group": RG}],
            ),
            RG: ResourceGroupConfig(
                limits={"node_num": 0},
                transfer_from=[{"resource_group": DEFAULT_RG}],
                transfer_to=[{"resource_group": DEFAULT_RG}],
            ),
        },
        "вариант 2: у rg requests=0 и limits=0": {
            RG: ResourceGroupConfig(
                requests={"node_num": 0},
                limits={"node_num": 0},
                transfer_from=[{"resource_group": DEFAULT_RG}],
                transfer_to=[{"resource_group": DEFAULT_RG}],
            ),
        },
    }

    for title, cfg in attempts.items():
        try:
            c.update_resource_groups(cfg)
            show(c, f"ПОСЛЕ «{title}»")
            if c.describe_resource_group(name=DEFAULT_RG).num_available_node > 0:
                print(f"  -> сработал {title}")
                break
        except Exception as exc:  # noqa: BLE001
            print(f"  [{title}] ошибка: {type(exc).__name__}: {str(exc)[:160]}")
    else:
        print("  откат через update_resource_groups не удался — пробуем transfer_node")
        try:
            from pymilvus import connections, utility

            connections.connect(alias="rg_restore", uri=c._using and "http://127.0.0.1:19530",
                                user="root", password="MilvusDemo123")
            utility.transfer_node(RG, DEFAULT_RG, 1, using="rg_restore")
            show(c, "ПОСЛЕ transfer_node")
        except Exception as exc:  # noqa: BLE001
            print(f"  transfer_node: {type(exc).__name__}: {str(exc)[:160]}")

    try:
        c.drop_resource_group(name=RG)
        print(f"группа {RG} удалена")
    except Exception as exc:  # noqa: BLE001
        print(f"drop {RG}: {type(exc).__name__}: {str(exc)[:120]}")

    # Контрольная проверка: коллекция создаётся, грузится и ищется
    name = "rg_restore_check"
    drop_if_exists(c, name)
    s = c.create_schema(auto_id=True, enable_dynamic_field=False)
    s.add_field("id", DataType.INT64, is_primary=True)
    s.add_field("v", DataType.FLOAT_VECTOR, dim=8)
    c.create_collection(collection_name=name, schema=s)
    ip = c.prepare_index_params()
    ip.add_index(field_name="v", index_type="FLAT", metric_type="COSINE")
    c.create_index(collection_name=name, index_params=ip)
    c.insert(name, [{"v": [0.1] * 8}])
    c.flush(collection_name=name)
    c.load_collection(collection_name=name)
    res = c.search(collection_name=name, data=[[0.1] * 8], limit=1)
    print(f"контроль: load+search работают, hits={len(res[0])}")
    drop_if_exists(c, name)
    show(c, "ИТОГ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())