"""Как ПОЧИНИТЬ код из отчёта: рабочие варианты проблемных мест.

Прогон на живом Milvus. Проверяются:
  A) коллекции-справочники без векторного поля (Clients/Currencies/Accounts/Cards);
  B) NULL в скалярном поле (card_id = None);
  D) эквивалентность L2 / IP / COSINE на нормализованных векторах (раздел 3.6.6);
  E) смена пароля пользователя (раздел 3.1.4).

Запуск:  python .\\verify\\probe_fix.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DataType, client, drop_if_exists, probe, report_vector, start_log, summary  # noqa: E402


def kv_variants(c) -> None:
    # A1 — как в отчёте: справочник без вектора
    drop_if_exists(c, "fix_currencies_report")
    with probe("A1 справочник БЕЗ векторного поля — как в отчёте (ожидаем ошибку)", expect_fail=True):
        s = c.create_schema(auto_id=False, enable_dynamic_field=False)
        s.add_field("currency_code", DataType.VARCHAR, max_length=3, is_primary=True)
        s.add_field("currency_name", DataType.VARCHAR, max_length=50)
        c.create_collection(collection_name="fix_currencies_report", schema=s)

    # A2 — рабочий вариант: техническое векторное поле dim=2 + FLAT
    drop_if_exists(c, "fix_currencies_ok")
    with probe("A2 справочник с техническим вектором dim=2 + FLAT (рабочий вариант)"):
        s = c.create_schema(auto_id=False, enable_dynamic_field=False)
        s.add_field("currency_code", DataType.VARCHAR, max_length=3, is_primary=True)
        s.add_field("numeric_code", DataType.INT32)
        s.add_field("currency_name", DataType.VARCHAR, max_length=50)
        s.add_field("symbol", DataType.VARCHAR, max_length=5)
        s.add_field("_tech_vector", DataType.FLOAT_VECTOR, dim=2)  # обязательная «заглушка»
        c.create_collection(collection_name="fix_currencies_ok", schema=s)
        ip = c.prepare_index_params()
        ip.add_index(field_name="_tech_vector", index_type="FLAT", metric_type="COSINE")
        c.create_index(collection_name="fix_currencies_ok", index_params=ip)
        c.insert("fix_currencies_ok", [
            {"currency_code": "RUB", "numeric_code": 643, "currency_name": "Российский рубль",
             "symbol": "₽", "_tech_vector": [0.0, 0.0]},
            {"currency_code": "USD", "numeric_code": 840, "currency_name": "Доллар США",
             "symbol": "$", "_tech_vector": [0.0, 0.0]},
        ])
        c.flush(collection_name="fix_currencies_ok")
        c.load_collection(collection_name="fix_currencies_ok")
        rows = c.query("fix_currencies_ok", filter='currency_code == "RUB"',
                       output_fields=["currency_name", "numeric_code"])
        print(f"  query по справочнику: {rows}")

    # A3 — динамическая схема без вектора
    drop_if_exists(c, "fix_dynamic_novec")
    with probe("A3 динамическая схема (enable_dynamic_field=True) без вектора (ожидаем ошибку)", expect_fail=True):
        s = c.create_schema(auto_id=False, enable_dynamic_field=True)
        s.add_field("currency_code", DataType.VARCHAR, max_length=3, is_primary=True)
        c.create_collection(collection_name="fix_dynamic_novec", schema=s)


def null_variants(c) -> None:
    # B1 — как в отчёте
    drop_if_exists(c, "fix_tx_report")
    with probe("B1 insert card_id=None без nullable — как в отчёте (ожидаем ошибку)", expect_fail=True):
        s = c.create_schema(auto_id=True, enable_dynamic_field=False)
        s.add_field("transaction_id", DataType.INT64, is_primary=True)
        s.add_field("account_id", DataType.INT64)
        s.add_field("card_id", DataType.INT64)
        s.add_field("purpose_vector", DataType.FLOAT_VECTOR, dim=8)
        c.create_collection(collection_name="fix_tx_report", schema=s)
        ip = c.prepare_index_params()
        ip.add_index(field_name="purpose_vector", index_type="FLAT", metric_type="COSINE")
        c.create_index(collection_name="fix_tx_report", index_params=ip)
        c.load_collection(collection_name="fix_tx_report")
        c.insert("fix_tx_report", [{"account_id": 1, "card_id": None,
                                    "purpose_vector": report_vector(8, seed=3)}])

    # B2 — nullable=True (Milvus 2.6+/3.0)
    drop_if_exists(c, "fix_tx_nullable")
    with probe("B2 insert card_id=None при nullable=True (рабочий вариант)"):
        s = c.create_schema(auto_id=True, enable_dynamic_field=False)
        s.add_field("transaction_id", DataType.INT64, is_primary=True)
        s.add_field("account_id", DataType.INT64)
        s.add_field("card_id", DataType.INT64, nullable=True)
        s.add_field("mcc", DataType.VARCHAR, max_length=4, nullable=True)
        s.add_field("purpose_vector", DataType.FLOAT_VECTOR, dim=8)
        c.create_collection(collection_name="fix_tx_nullable", schema=s)
        ip = c.prepare_index_params()
        ip.add_index(field_name="purpose_vector", index_type="FLAT", metric_type="COSINE")
        c.create_index(collection_name="fix_tx_nullable", index_params=ip)
        c.insert("fix_tx_nullable", [{"account_id": 1, "card_id": None, "mcc": None,
                                      "purpose_vector": report_vector(8, seed=3)}])
        c.flush(collection_name="fix_tx_nullable")
        c.load_collection(collection_name="fix_tx_nullable")
        print(f"  прочитано: {c.query('fix_tx_nullable', filter='account_id == 1', output_fields=['card_id', 'mcc'])}")
        print(f"  фильтр 'card_id is null' -> {c.query('fix_tx_nullable', filter='card_id is null', output_fields=['account_id'])}")

    # B3 — сентинел 0 (если nullable недоступен)
    drop_if_exists(c, "fix_tx_sentinel")
    with probe("B3 сентинел card_id=0 вместо NULL (альтернатива)"):
        s = c.create_schema(auto_id=True, enable_dynamic_field=False)
        s.add_field("transaction_id", DataType.INT64, is_primary=True)
        s.add_field("account_id", DataType.INT64)
        s.add_field("card_id", DataType.INT64)
        s.add_field("purpose_vector", DataType.FLOAT_VECTOR, dim=8)
        c.create_collection(collection_name="fix_tx_sentinel", schema=s)
        ip = c.prepare_index_params()
        ip.add_index(field_name="purpose_vector", index_type="FLAT", metric_type="COSINE")
        c.create_index(collection_name="fix_tx_sentinel", index_params=ip)
        c.insert("fix_tx_sentinel", [{"account_id": 1, "card_id": 0,
                                      "purpose_vector": report_vector(8, seed=3)}])
        c.flush(collection_name="fix_tx_sentinel")
        c.load_collection(collection_name="fix_tx_sentinel")
        print("  вставка с card_id=0 прошла")




def metric_equivalence(c) -> None:
    """Раздел 3.6.6: на нормализованных векторах L2/COSINE дают один порядок."""
    import numpy as np

    dim, n = 64, 200
    rng = np.random.default_rng(42)
    base = rng.normal(size=(n, dim)).astype("float32")
    base /= np.linalg.norm(base, axis=1, keepdims=True)  # нормализация, как в отчёте
    query = base[7]

    tops = {}
    for metric in ("L2", "IP", "COSINE"):
        name = f"fix_metric_{metric.lower()}"
        drop_if_exists(c, name)
        s = c.create_schema(auto_id=False, enable_dynamic_field=False)
        s.add_field("id", DataType.INT64, is_primary=True)
        s.add_field("v", DataType.FLOAT_VECTOR, dim=dim)
        c.create_collection(collection_name=name, schema=s)
        ip = c.prepare_index_params()
        ip.add_index(field_name="v", index_type="FLAT", metric_type=metric)
        c.create_index(collection_name=name, index_params=ip)
        c.insert(name, [{"id": i, "v": base[i].tolist()} for i in range(n)])
        c.flush(collection_name=name)
        c.load_collection(collection_name=name)
        res = c.search(collection_name=name, data=[query.tolist()], limit=10,
                       output_fields=["id"], search_params={"metric_type": metric})
        ids = [h["id"] for h in res[0]]
        tops[metric] = ids
        print(f"  {metric:<7} top-10 id: {ids} | score[0] = {res[0][0]['distance']:.4f}")

    print(f"\n  L2 top-10 == COSINE top-10 : {tops['L2'] == tops['COSINE']}")
    print(f"  IP top-10 == COSINE top-10 : {tops['IP'] == tops['COSINE']}")


def user_password(c) -> None:
    with probe("E3.1.4 create_user + update_password (смена пароля пользователя)"):
        try:
            c.drop_user(user_name="fix_pwd_user")
        except Exception:  # noqa: BLE001
            pass
        c.create_user(user_name="fix_pwd_user", password="OldPass123!")
        c.update_password(user_name="fix_pwd_user", old_password="OldPass123!",
                          new_password="NewPass123!")
        cc = client(user="fix_pwd_user", password="NewPass123!")
        print(f"  подключение с новым паролем: ok, версия сервера {cc.get_server_version()}")
        c.drop_user(user_name="fix_pwd_user")


def main() -> int:
    start_log(__file__)
    c = client()
    kv_variants(c)
    null_variants(c)
    metric_equivalence(c)
    user_password(c)

    for name in ("fix_currencies_report", "fix_currencies_ok", "fix_dynamic_novec",
                 "fix_tx_report", "fix_tx_nullable", "fix_tx_sentinel",
                 "fix_metric_l2", "fix_metric_ip", "fix_metric_cosine"):
        drop_if_exists(c, name)

    return summary()


if __name__ == "__main__":
    raise SystemExit(main())
