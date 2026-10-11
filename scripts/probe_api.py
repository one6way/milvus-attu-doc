"""Прогон кода из отчёта (главы 2-3) НА ЖИВОМ Milvus v3.0.1.

Каждый блок — код, дословно взятый из отчёта. Задача: показать, что реально
работает, а что падает (и с какой ошибкой Milvus).

Запуск:  python .\\verify\\probe_api.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    DataType,
    client,
    drop_if_exists,
    probe,
    report_vector,
    start_log,
    summary,
)

TAG = "probe_"  # префикс своих коллекций, чтобы не мешать рабочим


def p(name: str) -> str:
    return TAG + name


def main() -> int:
    start_log(__file__)
    c = client()

    # ---------- 3.2.1 Подключение и версия сервера ----------
    with probe("3.2.1 MilvusClient(uri, user, password) + версия сервера"):
        info = c.get_server_version()
        print(f"server_version = {info}")

    # ---------- 3.2.2 Создание BankingProducts (код из отчёта) ----------
    drop_if_exists(c, p("BankingProducts"))
    with probe("3.2.2 create_schema + 9 add_field + create_collection(BankingProducts)"):
        schema_products = c.create_schema(auto_id=True, enable_dynamic_field=False)
        schema_products.add_field("product_id", DataType.INT64, is_primary=True)
        schema_products.add_field("product_code", DataType.VARCHAR, max_length=20)
        schema_products.add_field("product_name", DataType.VARCHAR, max_length=150)
        schema_products.add_field("description", DataType.VARCHAR, max_length=2000)
        schema_products.add_field("product_type", DataType.VARCHAR, max_length=20)
        schema_products.add_field("interest_rate", DataType.FLOAT)
        schema_products.add_field("term_months", DataType.INT32)
        schema_products.add_field("service_cost", DataType.FLOAT)
        schema_products.add_field("description_vector", DataType.FLOAT_VECTOR, dim=768)
        c.create_collection(collection_name=p("BankingProducts"), schema=schema_products)

    # ---------- 3.2.3 Индексы (HNSW + INVERTED + STL_SORT) ----------
    with probe("3.2.3 prepare_index_params: HNSW + INVERTED(product_type) + STL_SORT(interest_rate)"):
        index_params = c.prepare_index_params()
        index_params.add_index(
            field_name="description_vector",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 200},
        )
        index_params.add_index(field_name="product_type", index_type="INVERTED")
        index_params.add_index(field_name="interest_rate", index_type="STL_SORT")
        c.create_index(collection_name=p("BankingProducts"), index_params=index_params)

# ---------- Коллекция Transactions (раздел 2.6.2) ----------
    drop_if_exists(c, p("Transactions"))
    with probe("2.6.2 create_collection(Transactions) + индексы HNSW/INVERTED/STL_SORT"):
        s = c.create_schema(auto_id=True, enable_dynamic_field=False)
        s.add_field("transaction_id", DataType.INT64, is_primary=True)
        s.add_field("account_id", DataType.INT64)
        s.add_field("card_id", DataType.INT64)
        s.add_field("transaction_date", DataType.VARCHAR, max_length=19)
        s.add_field("amount_minor", DataType.INT64)
        s.add_field("currency_code", DataType.VARCHAR, max_length=3)
        s.add_field("operation_type", DataType.VARCHAR, max_length=20)
        s.add_field("purpose", DataType.VARCHAR, max_length=500)
        s.add_field("mcc", DataType.VARCHAR, max_length=4)
        s.add_field("purpose_vector", DataType.FLOAT_VECTOR, dim=768)
        c.create_collection(collection_name=p("Transactions"), schema=s)
        ip = c.prepare_index_params()
        ip.add_index(
            field_name="purpose_vector",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 200},
        )
        ip.add_index(field_name="account_id", index_type="INVERTED")
        ip.add_index(field_name="operation_type", index_type="INVERTED")
        ip.add_index(field_name="mcc", index_type="INVERTED")
        ip.add_index(field_name="amount_minor", index_type="STL_SORT")
        c.create_index(collection_name=p("Transactions"), index_params=ip)

    # ---------- Остальные 4 коллекции ----------
    drop_if_exists(c, p("Currencies"))
    with probe("2.3.3 create_collection(Currencies) с VARCHAR primary key"):
        s = c.create_schema(auto_id=False, enable_dynamic_field=False)
        s.add_field("currency_code", DataType.VARCHAR, max_length=3, is_primary=True)
        s.add_field("numeric_code", DataType.INT32)
        s.add_field("currency_name", DataType.VARCHAR, max_length=50)
        s.add_field("symbol", DataType.VARCHAR, max_length=5)
        c.create_collection(collection_name=p("Currencies"), schema=s)

    for name, fields in (
        (
            "Clients",
            [
                ("client_id", DataType.INT64, {"is_primary": True}),
                ("full_name", DataType.VARCHAR, {"max_length": 150}),
                ("birth_date", DataType.VARCHAR, {"max_length": 10}),
                ("passport_series", DataType.VARCHAR, {"max_length": 4}),
                ("passport_number", DataType.VARCHAR, {"max_length": 6}),
                ("inn", DataType.VARCHAR, {"max_length": 12}),
                ("address", DataType.VARCHAR, {"max_length": 255}),
                ("phone", DataType.VARCHAR, {"max_length": 11}),
                ("email", DataType.VARCHAR, {"max_length": 320}),
                ("registration_date", DataType.VARCHAR, {"max_length": 10}),
            ],
        ),
        (
            "Accounts",
            [
                ("account_id", DataType.INT64, {"is_primary": True}),
                ("account_number", DataType.VARCHAR, {"max_length": 20}),
                ("client_id", DataType.INT64, {}),
                ("currency_code", DataType.VARCHAR, {"max_length": 3}),
                ("account_type", DataType.VARCHAR, {"max_length": 20}),
                ("status", DataType.VARCHAR, {"max_length": 20}),
                ("balance_minor", DataType.INT64, {}),
                ("open_date", DataType.VARCHAR, {"max_length": 10}),
            ],
        ),
        (
            "Cards",
            [
                ("card_id", DataType.INT64, {"is_primary": True}),
                ("card_number", DataType.VARCHAR, {"max_length": 16}),
                ("account_id", DataType.INT64, {}),
                ("product_id", DataType.INT64, {}),
                ("payment_system", DataType.VARCHAR, {"max_length": 20}),
                ("card_type", DataType.VARCHAR, {"max_length": 20}),
                ("expiry_date", DataType.VARCHAR, {"max_length": 7}),
                ("status", DataType.VARCHAR, {"max_length": 20}),
            ],
        ),
    ):
        drop_if_exists(c, p(name))
        with probe(f"2.3 create_collection({name})"):
            s = c.create_schema(auto_id=True, enable_dynamic_field=False)
            for fname, ftype, kwargs in fields:
                s.add_field(fname, ftype, **kwargs)
            c.create_collection(collection_name=p(name), schema=s)

# ---------- 3.3.3 insert (auto_id=True, dict без PK) ----------
    with probe("3.3.3 insert(BankingProducts) словарями без product_id (auto_id)"):
        data = [
            {
                "product_code": f"DEP{i:03d}",
                "product_name": f"Вклад тест {i}",
                "description": "Выгодный вклад с высокой ставкой и возможностью снятия",
                "product_type": "deposit",
                "interest_rate": 9.0 + i,
                "term_months": 12,
                "service_cost": 0.0,
                "description_vector": report_vector(768, seed=i),
            }
            for i in range(3)
        ]
        res = c.insert(collection_name=p("BankingProducts"), data=data)
        print(f"insert_count = {res['insert_count']}")

    with probe("3.3.3 flush + load_collection"):
        c.flush(collection_name=p("BankingProducts"))
        c.load_collection(collection_name=p("BankingProducts"))

    # ---------- 2.9.1 / 3.4.1 search с фильтром ----------
    with probe('3.4.1 search: filter=\'product_type == "deposit" and interest_rate > 8.0\''):
        results = c.search(
            collection_name=p("BankingProducts"),
            data=[report_vector(768, seed=1)],
            limit=5,
            output_fields=["product_name", "product_type", "interest_rate", "term_months"],
            search_params={"metric_type": "COSINE", "params": {"ef": 64}},
            filter='product_type == "deposit" and interest_rate > 8.0',
        )
        for hit in results[0]:
            print(f"  {hit['entity']['product_name']} — {hit['entity']['interest_rate']}% — dist={hit['distance']:.4f}")
        print(f"  всего найдено: {len(results[0])}")

    # ---------- 3.5.2 проверка доступа: zero-вектор ----------
    with probe("3.5.2 search(data=[[0.0]*768], limit=1) нулевым вектором"):
        r = c.search(collection_name=p("BankingProducts"), data=[[0.0] * 768], limit=1)
        print(f"  hits = {len(r[0])}")

    # ---------- 3.4.3 query векторного поля ----------
    with probe('3.4.3 query(output_fields=["purpose_vector"]) — вектор в output_fields'):
        c.insert(
            collection_name=p("Transactions"),
            data=[
                {
                    "account_id": 42,
                    "card_id": 1,
                    "transaction_date": "2026-01-15 10:00:00",
                    "amount_minor": 123456,
                    "currency_code": "RUB",
                    "operation_type": "purchase",
                    "purpose": "Оплата ЖКХ за декабрь",
                    "mcc": "4900",
                    "purpose_vector": report_vector(768, seed=5),
                }
            ],
        )
        c.flush(collection_name=p("Transactions"))
        c.load_collection(collection_name=p("Transactions"))
        rows = c.query(
            collection_name=p("Transactions"),
            filter="account_id == 42",
            output_fields=["purpose_vector"],
        )
        print(f"  получено строк: {len(rows)}")
        if rows:
            v = rows[0]["purpose_vector"]
            print(f"  тип вектора: {type(v).__name__}, длина: {len(v) if hasattr(v, '__len__') else 'n/a'}")

        import numpy as np

        vectors = [r["purpose_vector"] for r in rows]
        if vectors:
            avg = np.mean(vectors, axis=0)
            print(f"  np.mean(purpose_vector) -> shape {np.asarray(avg).shape} (работает)")

    # ---------- SCHEMA: enable_dynamic_field=False + лишнее поле ----------
    with probe("3.3.3 insert с лишним полем при enable_dynamic_field=False (ожидаем ошибку)", expect_fail=True):
        c.insert(
            collection_name=p("BankingProducts"),
            data=[{
                "product_code": "X", "product_name": "X", "description": "d",
                "product_type": "deposit", "interest_rate": 1.0, "term_months": 1,
                "service_cost": 0.0, "description_vector": report_vector(768, seed=9),
                "unknown_field": "boom",
            }],
        )

    # ---------- NULL в скалярном поле ----------
    with probe("2.6.1 insert с card_id=None (NULL в скалярном поле)"):
        c.insert(
            collection_name=p("Transactions"),
            data=[{
                "account_id": 43, "card_id": None, "transaction_date": "2026-01-01 00:00:00",
                "amount_minor": 100, "currency_code": "RUB", "operation_type": "transfer",
                "purpose": "Перевод", "mcc": None, "purpose_vector": report_vector(768, seed=7),
            }],
        )

    # ---------- Фильтр по VARCHAR с INVERTED ----------
    with probe('2.6.2 search с фильтром mcc == "4900" (INVERTED на VARCHAR(4))'):
        r = c.search(
            collection_name=p("Transactions"),
            data=[report_vector(768, seed=5)],
            limit=3,
            output_fields=["purpose", "mcc", "amount_minor"],
            search_params={"metric_type": "COSINE", "params": {"ef": 64}},
            filter='mcc == "4900"',
        )
        print(f"  hits = {len(r[0])}")

    # ---------- Уборка ----------
    for name in ("BankingProducts", "Transactions", "Clients", "Currencies", "Accounts", "Cards"):
        drop_if_exists(c, p(name))

    return summary()


if __name__ == "__main__":
    raise SystemExit(main())
