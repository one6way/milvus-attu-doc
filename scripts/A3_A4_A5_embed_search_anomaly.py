"""Проверка раздела 2.5 отчёта: реальная модель intfloat/multilingual-e5-base.

Проверяем на живом Milvus + реальной модели:
  * размерность эмбеддинга (768) и единичная норма при normalize_embeddings=True;
  * префиксы query:/passage: (влияют ли на ранжирование);
  * семантический поиск банковских продуктов с фильтром (раздел 2.9.1/3.4.1);
  * поиск похожих назначений платежей (раздел 3.4.2);
  * центроид транзакций и «аномалия по косинусному расстоянию» (раздел 3.4.3);
  * эквивалентность L2 / IP / COSINE на реальных нормализованных эмбеддингах (3.6.6).

Запуск:  python .\\verify\\probe_embed.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DataType, client, drop_if_exists, start_log  # noqa: E402

MODEL_NAME = "intfloat/multilingual-e5-base"
COLL = "probe_embed_products"
TX = "probe_embed_tx"

PRODUCTS = [
    ("DEP001", "Вклад «Максимальный доход»", "deposit", 11.5, 12,
     "Выгодный вклад с высокой ставкой до 11,5% годовых, без частичного снятия, капитализация процентов"),
    ("DEP002", "Вклад «Стабильный рост»", "deposit", 10.0, 6,
     "Срочный вклад на 6 месяцев со ставкой 10% годовых и капитализацией процентов"),
    ("DEP003", "Вклад «Гибкий»", "deposit", 9.5, 24,
     "Вклад с возможностью частичного снятия и пополнения, ставка 9,5% на два года"),
    ("DEP004", "Вклад «Пенсионный»", "deposit", 8.2, 36,
     "Вклад для пенсионеров с повышенной ставкой и возможностью снятия без потери процентов"),
    ("CRD001", "Кредит «Наличными»", "credit", 19.9, 60,
     "Потребительский кредит наличными до 5 миллионов рублей на срок до 5 лет, ставка от 19,9%"),
    ("CRD002", "Кредит «Авто»", "credit", 16.5, 84,
     "Автокредит на покупку нового автомобиля, ставка от 16,5% годовых, срок до 7 лет"),
    ("CRC001", "Дебетовая карта «Кэшбэк»", "card", 0.0, 0,
     "Дебетовая карта с кэшбэком до 5% на покупки, бесплатное обслуживание, снятие наличных без комиссии"),
    ("CRC002", "Дебетовая карта «Премиум»", "card", 0.0, 0,
     "Премиальная дебетовая карта с повышенным кэшбэком, страховкой путешествий и доступом в бизнес-залы"),
]

PURPOSES = [
    ("2026-01-15", 123450, "Оплата ЖКХ за декабрь", "4900"),
    ("2026-02-10", 98700, "Коммунальные платежи", "4900"),
    ("2026-01-20", 45000, "Оплата электроэнергии", "4900"),
    ("2026-03-05", 72000, "Квартплата за февраль", "4900"),
    ("2026-02-28", 31000, "Оплата воды и отопления", "4900"),
    ("2026-02-14", 560000, "Покупка бытовой техники в магазине", "5732"),
    ("2026-03-01", 250000, "Перевод другу на карту", "4829"),
    ("2026-03-11", 1200, "Кофе и завтрак в кафе", "5814"),
]

def main() -> int:
    start_log(__file__)
    c = client()

    from sentence_transformers import SentenceTransformer

    print(f"\n=== Загрузка модели {MODEL_NAME} ===")
    t0 = time.perf_counter()
    model = SentenceTransformer(MODEL_NAME)
    print(f"  загружена за {time.perf_counter() - t0:.1f} c; max_seq_length={model.max_seq_length}")

    def embed_passage(text: str):
        return model.encode(f"passage: {text}", normalize_embeddings=True)

    def embed_query(text: str):
        return model.encode(f"query: {text}", normalize_embeddings=True)

    import numpy as np

    v = embed_passage("Выгодный вклад с высокой ставкой")
    print("\n=== 2.5 размерность и норма вектора ===")
    print(f"  shape = {v.shape} (в отчёте заявлено 768)")
    print(f"  ||v|| = {float(np.linalg.norm(v)):.6f} (normalize_embeddings=True -> 1.0)")

    # ---------- Коллекция продуктов + HNSW/COSINE ----------
    drop_if_exists(c, COLL)
    s = c.create_schema(auto_id=True, enable_dynamic_field=False)
    s.add_field("product_id", DataType.INT64, is_primary=True)
    s.add_field("product_code", DataType.VARCHAR, max_length=20)
    s.add_field("product_name", DataType.VARCHAR, max_length=150)
    s.add_field("description", DataType.VARCHAR, max_length=2000)
    s.add_field("product_type", DataType.VARCHAR, max_length=20)
    s.add_field("interest_rate", DataType.FLOAT)
    s.add_field("term_months", DataType.INT32)
    s.add_field("description_vector", DataType.FLOAT_VECTOR, dim=768)
    c.create_collection(collection_name=COLL, schema=s)

    ip = c.prepare_index_params()
    ip.add_index(field_name="description_vector", index_type="HNSW", metric_type="COSINE",
                 params={"M": 16, "efConstruction": 200})
    ip.add_index(field_name="product_type", index_type="INVERTED")
    ip.add_index(field_name="interest_rate", index_type="STL_SORT")
    c.create_index(collection_name=COLL, index_params=ip)

    t0 = time.perf_counter()
    c.insert(COLL, [{
        "product_code": code,
        "product_name": name,
        "description": desc,
        "product_type": ptype,
        "interest_rate": rate,
        "term_months": term,
        "description_vector": embed_passage(desc).tolist(),
    } for code, name, ptype, rate, term, desc in PRODUCTS])
    print(f"\n=== 3.3.3 эмбеддинги {len(PRODUCTS)} продуктов за {time.perf_counter() - t0:.1f} c ===")
    c.flush(collection_name=COLL)
    c.load_collection(collection_name=COLL)

# ---------- 3.4.1 семантический поиск продуктов ----------
    print("\n=== 3.4.1 семантический поиск продуктов ===")
    query = "Выгодный вклад с высокой ставкой и возможностью снятия"
    for label, qvec in (
        ("С префиксом query: (как в отчёте)", embed_query(query).tolist()),
        ("БЕЗ префикса", model.encode(query, normalize_embeddings=True).tolist()),
    ):
        res = c.search(collection_name=COLL, data=[qvec], limit=5,
                       output_fields=["product_name", "product_type", "interest_rate"],
                       search_params={"metric_type": "COSINE", "params": {"ef": 64}})
        print(f"  [{label}]")
        for hit in res[0]:
            e = hit["entity"]
            print(f"    {e['product_name']:<32} {e['product_type']:<8} "
                  f"{e['interest_rate']:>5}% dist={hit['distance']:.4f}")

    res = c.search(collection_name=COLL, data=[embed_query(query).tolist()], limit=5,
                   output_fields=["product_name", "interest_rate", "term_months"],
                   search_params={"metric_type": "COSINE", "params": {"ef": 64}},
                   filter='product_type == "deposit" and interest_rate > 8.0')
    print('  [фильтр product_type == "deposit" and interest_rate > 8.0]')
    for hit in res[0]:
        e = hit["entity"]
        print(f"    {e['product_name']:<32} {e['interest_rate']:>5}% {e['term_months']} мес.")

    # ---------- Коллекция транзакций ----------
    drop_if_exists(c, TX)
    st = c.create_schema(auto_id=True, enable_dynamic_field=False)
    st.add_field("transaction_id", DataType.INT64, is_primary=True)
    st.add_field("account_id", DataType.INT64)
    st.add_field("transaction_date", DataType.VARCHAR, max_length=19)
    st.add_field("amount_minor", DataType.INT64)
    st.add_field("purpose", DataType.VARCHAR, max_length=500)
    st.add_field("mcc", DataType.VARCHAR, max_length=4)
    st.add_field("purpose_vector", DataType.FLOAT_VECTOR, dim=768)
    c.create_collection(collection_name=TX, schema=st)
    ipt = c.prepare_index_params()
    ipt.add_index(field_name="purpose_vector", index_type="HNSW", metric_type="COSINE",
                  params={"M": 16, "efConstruction": 200})
    c.create_index(collection_name=TX, index_params=ipt)
    c.insert(TX, [{
        "account_id": 42,
        "transaction_date": f"{d} 12:00:00",
        "amount_minor": amount,
        "purpose": purpose,
        "mcc": mcc,
        "purpose_vector": embed_passage(purpose).tolist(),
    } for d, amount, purpose, mcc in PURPOSES])
    c.flush(collection_name=TX)
    c.load_collection(collection_name=TX)

    print("\n=== 3.4.2 категоризация: поиск похожих назначений ===")
    res = c.search(collection_name=TX, data=[embed_query("Оплата коммунальных услуг").tolist()],
                   limit=5, output_fields=["transaction_date", "amount_minor", "purpose", "mcc"],
                   search_params={"metric_type": "COSINE", "params": {"ef": 64}})
    for hit in res[0]:
        e = hit["entity"]
        print(f"    {e['transaction_date'][:10]} | {e['purpose']:<38} | "
              f"{e['amount_minor'] / 100:>10.2f} | sim={hit['distance']:.4f}")

# ---------- 3.4.3 аномалии по центроиду ----------
    print("\n=== 3.4.3 аномалии: косинусное расстояние до центроида ===")
    rows = c.query(collection_name=TX, filter="account_id == 42",
                   output_fields=["purpose_vector", "purpose"])
    vectors = np.array([r["purpose_vector"] for r in rows], dtype="float32")
    centroid = vectors.mean(axis=0)
    centroid /= np.linalg.norm(centroid)
    sims = vectors @ centroid
    for row, sim in sorted(zip(rows, sims), key=lambda t: t[1]):
        flag = "АНОМАЛИЯ? " if sim < 0.75 else "          "
        print(f"    sim={sim:.4f} | {flag}{row['purpose'][:45]}")
    print(f"  тип центроида: {type(centroid).__name__}, shape = {centroid.shape}")

    # ---------- 3.6.6 эквивалентность метрик на реальных эмбеддингах ----------
    print("\n=== 3.6.6 L2 / IP / COSINE на реальных нормализованных эмбеддингах ===")
    texts = [p[5] for p in PRODUCTS] + [p[2] for p in PURPOSES]
    emb = model.encode([f"passage: {t}" for t in texts], normalize_embeddings=True)
    query_vec = embed_query("вклад с высокой ставкой")
    tops = {}
    for metric in ("L2", "IP", "COSINE"):
        name = f"probe_embed_{metric.lower()}"
        drop_if_exists(c, name)
        s2 = c.create_schema(auto_id=False, enable_dynamic_field=False)
        s2.add_field("id", DataType.INT64, is_primary=True)
        s2.add_field("v", DataType.FLOAT_VECTOR, dim=768)
        c.create_collection(collection_name=name, schema=s2)
        ip2 = c.prepare_index_params()
        ip2.add_index(field_name="v", index_type="FLAT", metric_type=metric)
        c.create_index(collection_name=name, index_params=ip2)
        c.insert(name, [{"id": i, "v": emb[i].tolist()} for i in range(len(texts))])
        c.flush(collection_name=name)
        c.load_collection(collection_name=name)
        r = c.search(collection_name=name, data=[query_vec.tolist()], limit=5,
                     output_fields=["id"], search_params={"metric_type": metric})
        tops[metric] = [h["id"] for h in r[0]]
        print(f"  {metric:<7} top-5 id: {tops[metric]}")
        drop_if_exists(c, name)
    print(f"  L2 == COSINE: {tops['L2'] == tops['COSINE']} | "
          f"IP == COSINE: {tops['IP'] == tops['COSINE']}")

    drop_if_exists(c, COLL)
    drop_if_exists(c, TX)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())