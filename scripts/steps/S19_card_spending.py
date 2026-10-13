# -*- coding: utf-8 -*-
"""ПРИМЕР: как сделать свою коллекцию с нуля под банковскую аналитику.

Коллекция `CardSpending` — траты клиентов по категориям (MCC). Скрипт полностью
самодостаточен: генерирует синтетические данные, создаёт схему и индексы, считает
эмбеддинги, загружает и показывает четыре способа анализа.

Файл написан как ОБРАЗЕЦ, который можно скопировать и переделать под свою задачу:
шаги подписаны в коде (`ШАГ 1 ... ШАГ 6`), а в комментариях — почему сделано именно так.

Запуск:
  .venv\\Scripts\\python.exe scripts\\steps\\S19_card_spending.py            # 300 трат, потом удалить коллекцию
  .venv\\Scripts\\python.exe scripts\\steps\\S19_card_spending.py --n 2000 --keep
"""
from __future__ import annotations

import argparse
import json
import os
import random
import urllib.request
from datetime import date, timedelta

from pymilvus import DataType, MilvusClient

# --- провайдер эмбеддингов: тот же, что у остальных шагов -------------------
API = os.environ.get("EMBED_API", "http://127.0.0.1:1234/v1/embeddings")
KEY = os.environ.get("EMBED_KEY", "sk-lm-local")
MODEL = os.environ.get("EMBED_MODEL", "text-embedding-nomic-embed-text-v1.5")
URI = os.environ.get("MILVUS_URI", "http://127.0.0.1:19530")
TOKEN = os.environ.get("MILVUS_TOKEN", "root:MilvusDemo123")

COLL = "CardSpending"
DIM = 768


def embed(texts: list[str], prefix: str) -> list[list[float]]:
    """Векторы для списка текстов (батчами — так быстрее)."""
    out: list[list[float]] = []
    for i in range(0, len(texts), 64):
        chunk = texts[i:i + 64]
        body = json.dumps({"model": MODEL,
                           "input": [prefix + t for t in chunk]}).encode()
        req = urllib.request.Request(API, data=body,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + KEY})
        with urllib.request.urlopen(req, timeout=180) as r:
            data = sorted(json.loads(r.read())["data"], key=lambda x: x["index"])
        out.extend([float(v) for v in x["embedding"]] for x in data)
    return out


# =============================================================================
# ШАГ 1. ДАННЫЕ: справочник категорий + генератор трат
# =============================================================================
# Категория -> (код MCC, торговые точки, шаблоны описаний, диапазон суммы в копейках)
# Замените этот словарь на свою предметную область (например, «переводы»,
# «подписки», «кредитные платежи») — остальной код менять не придётся.
CATEGORIES = {
    "Продукты и супермаркеты": (
        "5411", ["Пятёрочка", "Магнит", "Перекрёсток", "Ашан", "ВкусВилл"],
        ["оплата продуктов", "покупка продуктов на неделю", "продуктовая корзина",
         "покупка хлеба и молока", "закуп продуктов к празднику"],
        (30_000, 450_000)),          # 300 - 4 500 руб
    "Кафе и рестораны": (
        "5812", ["Кофемания", "Шоколадница", "Додо Пицца", "Тануки", "Вкусно и точка"],
        ["оплата обеда", "счёт за ужин", "кофе с собой", "бизнес-ланч", "доставка роллов"],
        (25_000, 380_000)),
    "Транспорт и такси": (
        "4121", ["Яндекс Такси", "Ситимобил", "Метро Москвы", "Аэроэкспресс", "Каршеринг Делимобиль"],
        ["оплата поездки на такси", "пополнение транспортной карты", "билет на метро",
         "поездка на каршеринге", "оплата проезда в автобусе"],
        (5_000, 240_000)),
    "Аптеки и здоровье": (
        "5912", ["Аптека Ригла", "Здоровые люди", "Аптека 36,6", "Медси", "Инвитро"],
        ["покупка лекарств", "оплата приёма врача", "сдача анализов", "покупка витаминов",
         "аптечный чек за медикаменты"],
        (15_000, 620_000)),
    "ЖКХ и связь": (
        "4900", ["Мосэнергосбыт", "Мосводоканал", "МТС", "Билайн", "Ростелеком"],
        ["оплата коммунальных услуг", "оплата электроэнергии", "взнос за содержание жилья",
         "оплата мобильной связи и интернета", "оплата отопления"],
        (40_000, 900_000)),
    "Одежда и обувь": (
        "5651", ["Спортмастер", "Zarina", "Wildberries", "Lamoda", "Ecco"],
        ["покупка кроссовок", "покупка зимней куртки", "заказ одежды онлайн",
         "покупка джинсов", "покупка обуви"],
        (80_000, 2_400_000)),
    "Развлечения": (
        "7995", ["Кино Октябрь", "Steam", "Театр Современник", "Фитнес Клуб", "Концертный зал"],
        ["покупка билетов в кино", "оплата подписки на игры", "билет в театр",
         "оплата годового абонемента в фитнес", "билет на концерт"],
        (30_000, 1_500_000)),
    "Путешествия": (
        "4722", ["Аэрофлот", "S7 Airlines", "Ostrovok", "РЖД", "Booking"],
        ["покупка авиабилета", "оплата брони отеля", "покупка билета на поезд",
         "оплата туристического тура", "оплата страховки путешественника"],
        (350_000, 12_000_000)),
}

CATEGORY_NAMES = list(CATEGORIES)


def gen_spends(n: int, seed: int) -> list[dict]:
    """Синтетические траты: детерминированы (seed), но выглядят правдоподобно.

    Использован тот же подход, что в scripts/create_banking_collections.py:
    random.seed(...) + случайный выбор из предметных списков. Так набор
    воспроизводим: при тех же n и seed получаются те же записи.
    """
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        cat = rng.choice(CATEGORY_NAMES)
        mcc, merchants, actions, (lo, hi) = CATEGORIES[cat]
        merchant = rng.choice(merchants)
        action = rng.choice(actions)
        amount = rng.randrange(lo, hi, 100)                 # кратно 1 рублю
        day = date(2026, 1, 1) + timedelta(days=rng.randrange(0, 120))
        rows.append({
            "client_id": rng.randrange(1000, 1030),
            "card_id": rng.choice([None, rng.randrange(1, 50)]),
            "spend_date": f"{day.isoformat()} {rng.randrange(8, 22):02d}:{rng.randrange(0, 60):02d}:00",
            "amount_minor": amount,
            "currency_code": "RUB",
            "merchant": merchant,
            "mcc": mcc,
            "category": cat,
            # текст для поиска: объединяем то, что важно по смыслу
            "description": f"{action} в {merchant}, категория {cat.lower()}, сумма {amount // 100} рублей",
        })
    return rows


# =============================================================================
# ШАГ 2. СХЕМА: описываем поля будущей коллекции
# =============================================================================
# Лимиты VARCHAR в БАЙТАХ (важно: кириллица в UTF-8 — 2 байта на символ).
# Держим их в одном месте, чтобы схема и проверка длин не расходились.
VARCHAR_LIMITS = {
    "currency_code": 3,
    "merchant": 100,
    "mcc": 4,
    "category": 60,
    "description": 600,
}


def create_collection(c: MilvusClient, recreate: bool = True) -> None:
    if c.has_collection(COLL) and recreate:
        c.drop_collection(COLL)
        print(f"[schema] прежняя коллекция {COLL} удалена")
    if c.has_collection(COLL):
        print(f"[schema] коллекция {COLL} уже существует — оставляю как есть")
        return

    s = c.create_schema(auto_id=True, enable_dynamic_field=False)
    # Первичный ключ: auto_id=True — Milvus сам нумерует записи
    s.add_field("spend_id", DataType.INT64, is_primary=True)
    s.add_field("client_id", DataType.INT64)
    s.add_field("card_id", DataType.INT64, nullable=True)   # часть трат — без карты
    s.add_field("spend_date", DataType.VARCHAR, max_length=19)
    s.add_field("amount_minor", DataType.INT64)             # копейки: деньги в целых числах
    for name, limit in VARCHAR_LIMITS.items():
        s.add_field(name, DataType.VARCHAR, max_length=limit)
    # Векторное поле — обязательный элемент любой коллекции Milvus (размерность модели 768)
    s.add_field("description_vector", DataType.FLOAT_VECTOR, dim=DIM)

    # =========================================================================
    # ШАГ 3. ИНДЕКСЫ: под каждый способ обращения к данным
    # =========================================================================
    idx = c.prepare_index_params()
    # (1) векторный индекс — для семантического поиска
    idx.add_index(field_name="description_vector", index_type="HNSW", metric_type="COSINE",
                  params={"M": 16, "efConstruction": 200})
    # (2) INVERTED — для быстрых точных фильтров по строковым полям
    for f in ("category", "mcc", "merchant"):
        idx.add_index(field_name=f, index_type="INVERTED")
    # (3) STL_SORT — для сравнений и сортировки по числам (диапазоны сумм)
    idx.add_index(field_name="amount_minor", index_type="STL_SORT")

    c.create_collection(collection_name=COLL, schema=s, index_params=idx)
    print(f"[schema] создана коллекция {COLL}: 11 полей, "
          f"индексы HNSW/COSINE + 3 x INVERTED + STL_SORT")


# =============================================================================
# ШАГ 4. ПРОВЕРКА ДЛИН, ЭМБЕДДИНГИ И ЗАГРУЗКА
# =============================================================================
def check_lengths(rows: list[dict]) -> None:
    """Проверяем, что тексты влезают в объявленные лимиты VARCHAR.

    Milvus считает max_length в БАЙТАХ: 20 кириллических символов = 39 байт.
    Лучше поймать это до вставки, чем получить
    'length of varchar field ... exceeds max length'.
    """
    print("[check] длины текстовых полей (байт UTF-8; кириллица = 2 байта на символ):")
    for name, limit in VARCHAR_LIMITS.items():
        worst = max(len(str(r.get(name) or "").encode("utf-8")) for r in rows)
        flag = "OK" if worst <= limit else "МАЛО!"
        print(f"    {name:<14} макс. {worst:>4} байт из {limit:>4}  {flag}")


def load(c: MilvusClient, rows: list[dict]) -> None:
    """Считаем эмбеддинги и вставляем записи."""
    vecs = embed([r["description"] for r in rows], "search_document: ")
    for r, v in zip(rows, vecs):
        r["description_vector"] = v
    res = c.insert(COLL, rows)
    c.flush(collection_name=COLL)
    c.load_collection(COLL)
    print(f"[load] вставлено {res.get('insert_count')} записей, коллекция загружена в память")


# =============================================================================
# ШАГ 5. АНАЛИЗ: то, ради чего коллекция и создавалась
# =============================================================================
def report(c: MilvusClient) -> None:
    total = c.query(COLL, filter="", output_fields=["count(*)"])[0]["count(*)"]
    print(f"\n1) РАСХОДЫ ПО КАТЕГОРИЯМ (query + group_by_fields, без выгрузки строк)")
    print(f"   всего трат: {total}")
    print(f"   {'категория':<26} {'трат':>5} {'сумма, руб':>12} {'доля, %':>8}")
    grp = c.query(COLL, filter="", output_fields=["category", "count(*)", "sum(amount_minor)"],
                  group_by_fields=["category"])
    grand = sum(g["sum(amount_minor)"] for g in grp)
    for g in sorted(grp, key=lambda x: -x["sum(amount_minor)"]):
        print(f"   {g['category']:<26} {g['count(*)']:>5} "
              f"{g['sum(amount_minor)'] / 100:>12,.2f} "
              f"{g['sum(amount_minor)'] / grand * 100:>7.1f}%")

    print("\n2) СЕМАНТИЧЕСКИЙ ПОИСК (вектор): 'крупная покупка одежды и обуви'")
    q = embed(["крупная покупка одежды и обуви"], "search_query: ")[0]
    for h in c.search(COLL, data=[q], anns_field="description_vector", limit=5,
                      search_params={"metric_type": "COSINE", "params": {"ef": 64}},
                      output_fields=["category", "merchant", "amount_minor", "spend_date"])[0]:
        e = h["entity"]
        print(f"   cos={h['distance']:.4f} | {e['category']:<24} {e['merchant']:<18} "
              f"{e['amount_minor'] / 100:>10,.2f} руб | {e['spend_date'][:10]}")

    print("\n3) ПОИСК С ФИЛЬТРОМ (скалярные условия): дорогие траты в кафе")
    for h in c.search(COLL, data=[q], anns_field="description_vector", limit=5,
                      filter='category == "Кафе и рестораны" and amount_minor > 100000',
                      output_fields=["category", "merchant", "amount_minor"])[0]:
        e = h["entity"]
        print(f"   cos={h['distance']:.4f} | {e['merchant']:<18} {e['amount_minor'] / 100:>10,.2f} руб")

    print("\n4) ПРОВЕРКА «СВОИМИ ГЛАЗАМИ» (первые 3 записи как есть)")
    for r in c.query(COLL, filter="", output_fields=["spend_date", "merchant", "mcc",
                                                     "category", "amount_minor"],
                     limit=3):
        print(f"   {r['spend_date']} | {r['merchant']:<18} | MCC {r['mcc']} | "
              f"{r['category']:<24} | {r['amount_minor'] / 100:>10,.2f} руб")

    print("\n5) ПРОВЕРКА КАЧЕСТВА: находит ли поиск ту категорию, которую мы ждём")
    checks = [
        ("поездки на такси по городу", "Транспорт и такси"),
        ("оплата интернета и мобильной связи", "ЖКХ и связь"),
        ("покупка продуктов на неделю в супермаркете", "Продукты и супермаркеты"),
        ("крупная покупка одежды и обуви", "Одежда и обувь"),
        ("потратил деньги на лекарства и приём врача", "Аптеки и здоровье"),
        ("купил билеты на самолёт и забронировал отель", "Путешествия"),
        ("сходил в кино и купил абонемент в спортзал", "Развлечения"),
    ]
    hits_ok = 0
    for text, expect in checks:
        found = c.search(COLL, data=[embed([text], "search_query: ")[0]],
                         anns_field="description_vector", limit=1,
                         output_fields=["category"])[0]
        got = found[0]["entity"]["category"] if found else "—"
        good = got == expect
        hits_ok += good
        print(f"   {'ok   ' if good else 'МИМО '} {text[:44]:<46} -> {got}")
    print(f"   итог: {hits_ok} из {len(checks)} запросов попали в ожидаемую категорию")
    print("   (если промах — это повод посмотреть на тексты описаний и на смежность категорий)")


# =============================================================================
# main: сборка всего вместе
# =============================================================================
def main() -> int:
    ap = argparse.ArgumentParser(description="Пример своей коллекции: траты по категориям.")
    ap.add_argument("--n", type=int, default=300, help="сколько трат сгенерировать")
    ap.add_argument("--seed", type=int, default=42, help="seed генератора (для повторяемости)")
    ap.add_argument("--keep", action="store_true", help="не удалять коллекцию в конце")
    args = ap.parse_args()

    print(f"модель эмбеддингов: {MODEL} ({API})")
    c = MilvusClient(uri=URI, token=TOKEN)
    print(f"сервер Milvus: {c.get_server_version()}")

    create_collection(c)
    if c.query(COLL, filter="", output_fields=["count(*)"])[0]["count(*)"] == 0:
        rows = gen_spends(args.n, args.seed)
        check_lengths(rows)
        load(c, rows)
    else:
        print("[load] данные уже есть — генерировать не нужно")

    report(c)

    if not args.keep:
        c.drop_collection(COLL)
        print(f"\n[cleanup] коллекция {COLL} удалена (флаг --keep оставляет её в Milvus)")
    else:
        print(f"\n[keep] коллекция {COLL} оставлена в Milvus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())