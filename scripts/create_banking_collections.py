# -*- coding: utf-8 -*-
"""Создать банковские коллекции из отчёта и залить тестовые данные.

Коллекции (по otchet.txt / OTCHET_V2.md):
  BankingProducts  — продукты (вектор description_vector, dim=768)
  Transactions     — проводки (вектор purpose_vector, dim=768)
  Currencies, Clients, Accounts, Cards — справочники (тех. поле _tech_vector dim=2)

Пример:
  python scripts/create_banking_collections.py \
    --api-base http://127.0.0.1:1234/v1 --api-key sk-lm-... \
    --api-model text-embedding-nomic-embed-text-v1.5 \
    --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123 --recreate
"""
import argparse, os, random, sys
from datetime import date, timedelta

import requests
from pymilvus import DataType, MilvusClient

REFS = ["Currencies", "Clients", "Accounts", "Cards"]
VECCOL = ["BankingProducts", "Transactions"]


def make_embedder(base_url, api_key, model, prefix="search_document: "):
    url = base_url.rstrip("/") + "/embeddings"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    def encode(texts):
        out = []
        for i in range(0, len(texts), 64):
            batch = [prefix + t for t in texts[i:i + 64]]
            r = requests.post(url, headers=headers, json={"model": model, "input": batch}, timeout=180)
            if r.status_code != 200:
                raise SystemExit(f"ERROR: embeddings API {r.status_code}: {r.text[:200]}")
            d = r.json()["data"]
            d.sort(key=lambda x: x.get("index", 0))
            out.extend([list(map(float, x["embedding"])) for x in d])
        return out
    return encode


def make_e5_embedder(model_name="intfloat/multilingual-e5-base", prefix="passage: "):
    """Локальный эмбеддер E5 (как в отчёте, раздел 3.3.1): префикс 'passage: ', normalize=True."""
    from sentence_transformers import SentenceTransformer
    print(f"[e5] model={model_name} prefix={prefix!r}", flush=True)
    model = SentenceTransformer(model_name)

    def encode(texts):
        vecs = model.encode([prefix + t for t in texts], normalize_embeddings=True, show_progress_bar=False)
        return [list(map(float, v)) for v in vecs]
    return encode


def build_parser():
    p = argparse.ArgumentParser(description="Банковские коллекции из отчёта -> Milvus.")
    p.add_argument("--api-base", default=os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:1234/v1"))
    p.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    p.add_argument("--api-model", default="text-embedding-nomic-embed-text-v1.5")
    p.add_argument("--host", default=os.environ.get("MILVUS_HOST", "127.0.0.1"))
    p.add_argument("--port", default=os.environ.get("MILVUS_PORT", "19530"))
    p.add_argument("--user", default=os.environ.get("MILVUS_USER", ""))
    p.add_argument("--password", default=os.environ.get("MILVUS_PASSWORD", ""))
    p.add_argument("--recreate", action="store_true")
    p.add_argument("--embedder", choices=["api", "e5"], default="api",
                   help="api — OpenAI-совместимый сервер (LM Studio); e5 — локальный intfloat/multilingual-e5-base")
    p.add_argument("--n-products", type=int, default=30)
    p.add_argument("--n-transactions", type=int, default=30)
    p.add_argument("--seed", type=int, default=42)
    return p


def create_products(c):
    s = c.create_schema(auto_id=True, enable_dynamic_field=False)
    s.add_field("product_id", DataType.INT64, is_primary=True)
    s.add_field("product_code", DataType.VARCHAR, max_length=20)
    s.add_field("product_name", DataType.VARCHAR, max_length=150)
    s.add_field("description", DataType.VARCHAR, max_length=2000)
    s.add_field("product_type", DataType.VARCHAR, max_length=20)
    s.add_field("interest_rate", DataType.FLOAT, nullable=True)
    s.add_field("term_months", DataType.INT32, nullable=True)
    s.add_field("service_cost", DataType.FLOAT, nullable=True)
    s.add_field("description_vector", DataType.FLOAT_VECTOR, dim=768)
    idx = c.prepare_index_params()
    idx.add_index("description_vector", index_type="HNSW", metric_type="COSINE",
                  params={"M": 16, "efConstruction": 200})
    idx.add_index("product_type", index_type="INVERTED")
    idx.add_index("interest_rate", index_type="STL_SORT")
    c.create_collection("BankingProducts", schema=s, index_params=idx)
    print("[create] BankingProducts")


def gen_products(n):
    types = ["deposit", "credit", "card"]
    names = {
        "deposit": ["Сберегательный вклад", "Накопительный счёт «Копилка»", "Вклад «Максимум»", "Вклад для пенсионеров"],
        "credit": ["Потребительский кредит", "Ипотека «Своё жильё»", "Автокредит", "Кредит «Рефинансирование»"],
        "card": ["Дебетовая карта «Мир»", "Карта «Кэшбэк 10%»", "Премиальная карта Platinum", "Зарплатная карта"],
    }
    prods = []
    for i in range(n):
        t = types[i % 3]
        nm = random.choice(names[t]) + f" {i+1:02d}"
        if t == "deposit":
            desc = (f"Вклад с процентной ставкой {random.choice([5.5, 6.0, 7.2, 8.1])}% годовых, "
                    f"минимальная сумма 10000 рублей, срок размещения от 3 до 36 месяцев, "
                    f"капитализация процентов ежемесячно. Подходит для сохранения и преумножения сбережений.")
            prods.append({"product_code": f"DEP{i+1:03d}", "product_name": nm, "product_type": "deposit",
                          "description": desc, "interest_rate": 7.2, "term_months": 12, "service_cost": None})
        elif t == "credit":
            desc = (f"Кредит наличными на сумму до 3 000 000 рублей под {random.choice([14.9, 17.5, 19.9])}% годовых, "
                    f"сроком до 60 месяцев, без залога и поручителей. Решение по заявке за 5 минут.")
            prods.append({"product_code": f"CRE{i+1:03d}", "product_name": nm, "product_type": "credit",
                          "description": desc, "interest_rate": 17.5, "term_months": 60, "service_cost": None})
        else:
            desc = ("Дебетовая карта с кэшбэком до 10% в категориях, бесплатным обслуживанием при обороте, "
                    "снятием наличных без комиссии, поддержкой бесконтактной оплаты и Apple Pay.")
            prods.append({"product_code": f"CARD{i+1:03d}", "product_name": nm, "product_type": "card",
                          "description": desc, "interest_rate": None, "term_months": None, "service_cost": 0.0})
    return prods


def create_transactions(c):
    s = c.create_schema(auto_id=True, enable_dynamic_field=False)
    s.add_field("transaction_id", DataType.INT64, is_primary=True)
    s.add_field("account_id", DataType.INT64)
    s.add_field("card_id", DataType.INT64, nullable=True)
    s.add_field("transaction_date", DataType.VARCHAR, max_length=19)
    s.add_field("amount_minor", DataType.INT64)
    s.add_field("currency_code", DataType.VARCHAR, max_length=3)
    s.add_field("operation_type", DataType.VARCHAR, max_length=20)
    s.add_field("purpose", DataType.VARCHAR, max_length=500, nullable=True)
    s.add_field("mcc", DataType.VARCHAR, max_length=4, nullable=True)
    s.add_field("purpose_vector", DataType.FLOAT_VECTOR, dim=768)
    idx = c.prepare_index_params()
    idx.add_index("purpose_vector", index_type="HNSW", metric_type="COSINE",
                  params={"M": 16, "efConstruction": 200})
    idx.add_index("account_id", index_type="INVERTED")
    idx.add_index("operation_type", index_type="INVERTED")
    idx.add_index("mcc", index_type="INVERTED")
    idx.add_index("amount_minor", index_type="STL_SORT")
    c.create_collection("Transactions", schema=s, index_params=idx)
    print("[create] Transactions")


PURPOSES = [
    "Оплата продуктов в супермаркете «Пятёрочка»",
    "Перевод заработной платы на счёт",
    "Оплата коммунальных услуг за электроэнергию",
    "Снятие наличных в банкомате",
    "Оплата мобильной связи и интернета",
    "Покупка авиабилетов в Москву",
    "Оплата в ресторане и кафе",
    "Перевод средств другому клиенту банка",
    "Оплата услуг ЖКХ и отопления",
    "Покупка лекарств в аптеке",
    "Оплата поездки на такси по карте",
    "Ежемесячный платёж по ипотеке",
]


def gen_transactions(n):
    txs = []
    for i in range(n):
        txs.append({
            "account_id": random.randint(1000, 2000),
            "card_id": random.choice([None, random.randint(1, 50)]),
            "transaction_date": (date(2025, 1, 1) + timedelta(days=i)).isoformat() + "T12:00:00",
            "amount_minor": random.randint(10000, 5000000),
            "currency_code": "RUB",
            "operation_type": random.choice(["debit", "credit", "transfer"]),
            "purpose": PURPOSES[i % len(PURPOSES)],
            "mcc": random.choice(["5411", "6011", "4814", "5812", "4111", None]),
        })
    return txs


def create_ref(c, name, fields, auto_id=True):
    if c.has_collection(name):
        return False
    s = c.create_schema(auto_id=auto_id, enable_dynamic_field=False)
    for fname, ftype, kw in fields:
        s.add_field(fname, ftype, **kw)
    s.add_field("_tech_vector", DataType.FLOAT_VECTOR, dim=2)
    idx = c.prepare_index_params()
    idx.add_index("_tech_vector", index_type="FLAT", metric_type="COSINE")
    c.create_collection(name, schema=s, index_params=idx)
    print(f"[create] {name}")
    return True


def ref_data():
    cur = [("RUB", 643, "Российский рубль", "₽"), ("USD", 840, "Доллар США", "$"),
           ("EUR", 978, "Евро", "€"), ("CNY", 156, "Китайский юань", "¥"),
           ("GBP", 826, "Фунт стерлингов", "£"), ("JPY", 392, "Японская иена", "¥"),
           ("KZT", 398, "Казахстанский тенге", "₸"), ("BYN", 933, "Белорусский рубль", "Br"),
           ("TRY", 949, "Турецкая лира", "₺"), ("CHF", 756, "Швейцарский франк", "₣")]
    currencies = [{"currency_code": a, "numeric_code": b, "currency_name": nm,
                   "symbol": s, "_tech_vector": [0.0, 0.0]} for a, b, nm, s in cur]

    names = ["Иванов Иван Иванович", "Петрова Мария Сергеевна", "Сидоров Алексей Петрович",
             "Кузнецова Анна Дмитриевна", "Смирнов Дмитрий Олегович", "Волкова Екатерина Андреевна",
             "Морозов Никита Владимирович", "Новикова Ольга Игоревна", "Фёдоров Павел Романович",
             "Соколова Дарья Максимовна"]
    clients = []
    for i, nm in enumerate(names, 1):
        clients.append({"client_id": i, "full_name": nm, "birth_date": f"19{70 + i}/0{1 + i % 9}/1{i % 9}",
                        "passport_series": f"{4500 + i}", "passport_number": f"{100000 + i}",
                        "inn": f"{770000000000 + i}", "address": f"г. Москва, ул. Примерная, д. {i}",
                        "phone": f"+7 (9{i % 10}{i % 8}) 12{i % 10}-4{i % 9}-{i}0",
                        "email": f"client{i}@example.ru",
                        "registration_date": f"20{10 + i % 10}-0{1 + i % 9}-1{i % 9}",
                        "_tech_vector": [0.0, 0.0]})

    accounts = []
    for i in range(1, 31):
        accounts.append({"account_id": i, "account_number": f"40817810{i:012d}",
                         "client_id": (i % 10) + 1, "currency_code": "RUB",
                         "account_type": ["current", "savings", "card"][i % 3], "status": "active",
                         "balance_minor": random.randint(100000, 90000000),
                         "open_date": f"20{15 + i % 10}-0{1 + i % 9}-1{i % 9}",
                         "_tech_vector": [0.0, 0.0]})

    cards = []
    for i in range(1, 21):
        cards.append({"card_id": i, "card_number": f"4276 {4000 + i % 100:04d} {5000 + i % 100:04d} {i:04d}",
                      "account_id": (i % 30) + 1, "product_id": None,
                      "payment_system": ["VISA", "MasterCard", "МИР"][i % 3],
                      "card_type": ["debit", "credit"][i % 2],
                      "expiry_date": f"0{1 + i % 9}/2{i % 10}", "status": "active",
                      "_tech_vector": [0.0, 0.0]})
    return currencies, clients, accounts, cards


def main(argv=None):
    args = build_parser().parse_args(argv)
    random.seed(args.seed)
    uri = args.host if args.host.startswith("http") else f"http://{args.host}:{args.port}"
    c = MilvusClient(uri=uri, token=(f"{args.user}:{args.password}" if args.user else ""))
    enc = make_e5_embedder() if args.embedder == "e5" else make_embedder(args.api_base, args.api_key, args.api_model)

    if args.recreate:
        for name in VECCOL + REFS:
            if c.has_collection(name):
                c.drop_collection(name)

    # 1) BankingProducts
    if not c.has_collection("BankingProducts"):
        create_products(c)
        prods = gen_products(args.n_products)
        vecs = enc([p["description"] for p in prods])
        for p, v in zip(prods, vecs):
            p["description_vector"] = v
        print(f"  вставлено products={c.insert('BankingProducts', prods).get('insert_count')}")

    # 2) Transactions
    if not c.has_collection("Transactions"):
        create_transactions(c)
        txs = gen_transactions(args.n_transactions)
        vecs = enc([t["purpose"] for t in txs])
        for t, v in zip(txs, vecs):
            t["purpose_vector"] = v
        print(f"  вставлено transactions={c.insert('Transactions', txs).get('insert_count')}")

    # 3) Справочники
    created = {}
    created["Currencies"] = create_ref(c, "Currencies", [
        ("currency_code", DataType.VARCHAR, {"max_length": 3, "is_primary": True}),
        ("numeric_code", DataType.INT32, {}),
        ("currency_name", DataType.VARCHAR, {"max_length": 50}),
        ("symbol", DataType.VARCHAR, {"max_length": 5}),
    ], auto_id=False)
    created["Clients"] = create_ref(c, "Clients", [
        ("client_id", DataType.INT64, {"is_primary": True}),
        ("full_name", DataType.VARCHAR, {"max_length": 150}),
        ("birth_date", DataType.VARCHAR, {"max_length": 10}),
        ("passport_series", DataType.VARCHAR, {"max_length": 4}),
        ("passport_number", DataType.VARCHAR, {"max_length": 6}),
        ("inn", DataType.VARCHAR, {"max_length": 12}),
        ("address", DataType.VARCHAR, {"max_length": 255}),
        ("phone", DataType.VARCHAR, {"max_length": 20}),
        ("email", DataType.VARCHAR, {"max_length": 320}),
        ("registration_date", DataType.VARCHAR, {"max_length": 10}),
    ], auto_id=False)
    created["Accounts"] = create_ref(c, "Accounts", [
        ("account_id", DataType.INT64, {"is_primary": True}),
        ("account_number", DataType.VARCHAR, {"max_length": 20}),
        ("client_id", DataType.INT64, {}),
        ("currency_code", DataType.VARCHAR, {"max_length": 3}),
        ("account_type", DataType.VARCHAR, {"max_length": 20}),
        ("status", DataType.VARCHAR, {"max_length": 20}),
        ("balance_minor", DataType.INT64, {}),
        ("open_date", DataType.VARCHAR, {"max_length": 10}),
    ], auto_id=False)
    created["Cards"] = create_ref(c, "Cards", [
        ("card_id", DataType.INT64, {"is_primary": True}),
        ("card_number", DataType.VARCHAR, {"max_length": 20}),
        ("account_id", DataType.INT64, {}),
        ("product_id", DataType.INT64, {"nullable": True}),
        ("payment_system", DataType.VARCHAR, {"max_length": 20}),
        ("card_type", DataType.VARCHAR, {"max_length": 20}),
        ("expiry_date", DataType.VARCHAR, {"max_length": 7}),
        ("status", DataType.VARCHAR, {"max_length": 20}),
    ], auto_id=False)

    currencies, clients, accounts, cards = ref_data()
    for name, rows in [("Currencies", currencies), ("Clients", clients),
                       ("Accounts", accounts), ("Cards", cards)]:
        if created.get(name):
            print(f"  вставлено {name}={c.insert(name, rows).get('insert_count')}")

    # 4) Load
    for name in VECCOL + REFS:
        try:
            c.load_collection(name)
        except Exception as e:
            print(f"[warn] load {name}: {e}")
    print("[done] коллекции:", c.list_collections())
    return 0


if __name__ == "__main__":
    sys.exit(main())


