"""Самотест из OTCHET_V2.md — проверяем, что он печатает именно то, что обещано."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DataType, MilvusClient, client, drop_if_exists, start_log  # noqa: E402


def main() -> int:
    start_log(__file__)
    c = client()
    print("версия Milvus:", c.get_server_version())

    # 1) коллекция без вектора НЕ создаётся
    drop_if_exists(c, "selfcheck_novec")
    try:
        s = c.create_schema(auto_id=False, enable_dynamic_field=False)
        s.add_field("k", DataType.INT64, is_primary=True)
        c.create_collection(collection_name="selfcheck_novec", schema=s)
        print("1) ОШИБКА: Milvus создал коллекцию без вектора!")
    except Exception as exc:  # noqa: BLE001
        print("1) коллекция без вектора отклонена (ок):", str(exc)[:80])

    # 2) NULL без nullable отклоняется — на ВРЕМЕННОЙ коллекции (чтобы не зависеть от наличия Transactions)
    drop_if_exists(c, "selfcheck_tx")
    s = c.create_schema(auto_id=True, enable_dynamic_field=False)
    s.add_field("transaction_id", DataType.INT64, is_primary=True)
    s.add_field("account_id", DataType.INT64)
    s.add_field("card_id", DataType.INT64)          # nullable НЕ указан
    s.add_field("purpose_vector", DataType.FLOAT_VECTOR, dim=8)
    c.create_collection(collection_name="selfcheck_tx", schema=s)
    idx = c.prepare_index_params()
    idx.add_index(field_name="purpose_vector", index_type="FLAT", metric_type="COSINE")
    c.create_index(collection_name="selfcheck_tx", index_params=idx)
    c.load_collection(collection_name="selfcheck_tx")
    try:
        c.insert("selfcheck_tx", [{"account_id": 1, "card_id": None,
                                   "purpose_vector": [0.0] * 8}])
        print("2) ОШИБКА: NULL прошёл без nullable!")
    except Exception as exc:  # noqa: BLE001
        print("2) NULL без nullable отклонён (ок):", str(exc)[:80])

    # 3) встроенная роль admin
    try:
        c.create_role(role_name="admin")
        print("3) ОШИБКА: роль admin удалось создать!")
    except Exception as exc:  # noqa: BLE001
        print("3) admin — встроенная роль (ок):", str(exc)[:80])

    drop_if_exists(c, "selfcheck_novec")
    drop_if_exists(c, "selfcheck_tx")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())