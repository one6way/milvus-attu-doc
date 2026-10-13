# -*- coding: utf-8 -*-
"""Дополнительный практический шаг: коллекция обращений клиентов SupportTickets.

Зачем нужна эта коллекция (сверх коллекций отчёта):
  1) показать ВТОРОЙ (после HNSW) способ поиска — полнотекстовый BM25 по sparse-вектору;
  2) показать ГИБРИДНЫЙ поиск: dense (эмбеддинг) + sparse (BM25) с объединением
     результатов ранкером RRFRanker — ключевая возможность Milvus 3.0;
  3) применить всё к третьей предметной области банка — обращениям в поддержку
     (карты, переводы, кредиты, вклады, безопасность, мобильное приложение).

Состав коллекции:
  ticket_id (PK, auto), client_id, channel, priority, status, created_at,
  subject, body (VARCHAR + enable_analyzer=True), category,
  body_vector (FLOAT_VECTOR dim=768 - эмбеддинг текста обращения),
  body_sparse (SPARSE_FLOAT_VECTOR - заполняется Milvus автоматически
               через Function(BM25) по полю body).

Индексы: HNSW/COSINE по body_vector, SPARSE_INVERTED_INDEX/BM25 по body_sparse,
INVERTED по channel/priority/category/status.

Эмбеддинги: тот же сервис, что и для коллекций отчёта (EMBED_API):
LM Studio на 127.0.0.1:1234/v1/embeddings либо локальный сервис
scripts/embed_server_local.py на порту 8091.

Запуск:
  .venv\\Scripts\\python.exe scripts\\steps\\S18_support_tickets.py
  .venv\\Scripts\\python.exe scripts\\steps\\S18_support_tickets.py --keep
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

from pymilvus import (AnnSearchRequest, DataType, Function, FunctionType,
                      MilvusClient, RRFRanker)

# --- эмбеддинги: тот же провайдер, что у остальных шагов --------------------
API = os.environ.get("EMBED_API", "http://127.0.0.1:1234/v1/embeddings")
KEY = os.environ.get("EMBED_KEY", "sk-lm-local")
MODEL = os.environ.get("EMBED_MODEL", "text-embedding-nomic-embed-text-v1.5")
URI = os.environ.get("MILVUS_URI", "http://127.0.0.1:19530")
TOKEN = os.environ.get("MILVUS_TOKEN", "root:MilvusDemo123")

COLL = "SupportTickets"
DIM = 768
KEEP = "--keep" in sys.argv

c = MilvusClient(uri=URI, token=TOKEN)


def embed(texts: list[str], prefix: str) -> list[list[float]]:
    """Векторы для списка текстов через OpenAI-совместимый /embeddings."""
    body = json.dumps({"model": MODEL, "input": [prefix + t for t in texts]}).encode()
    req = urllib.request.Request(API, data=body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + KEY})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = sorted(json.loads(r.read())["data"], key=lambda x: x["index"])
    return [[float(v) for v in x["embedding"]] for x in data]


# --- данные: 30 обращений клиентов -----------------------------------------
# поля: client_id, channel, priority, status, subject, category, body
TICKETS = [
    (1001, "mobile_app", "critical", "open", "Не проходит вход в приложение после обновления", "Мобильное приложение", "После обновления мобильного приложения банка вход по отпечатку не работает, приложение закрывается сразу после запуска. Пароль от личного кабинета в веб-версии подходит."),
    (1002, "call_center", "high", "in_progress", "Заблокирована карта из-за подозрительной операции", "Безопасность", "Карта заблокирована после попытки оплаты на неизвестном сайте. Прошу разблокировать карту и проверить операцию списания 12 500 рублей."),
    (1003, "web", "normal", "resolved", "Не пришёл перевод через СБП", "Переводы", "Перевод по системе быстрых платежей от 05.10 на сумму 30 000 рублей не зачислен на счёт получателя, хотя деньги списаны со счёта отправителя."),
    (1004, "branch", "normal", "resolved", "Какой процент по вкладу Максимальный доход", "Вклады", "Хочу уточнить ставку по вкладу Максимальный доход на 12 месяцев и возможность частичного снятия без потери процентов."),
    (1005, "atm", "high", "open", "Банкомат не выдал наличные, но деньги списались", "Карты", "При снятии наличных 10 000 рублей в банкомате по адресу Ленина 15 купюры не выданы, однако сумма списана со счёта карты."),
    (1006, "mobile_app", "normal", "resolved", "Не отображается кэшбэк за покупки", "Карты", "В приложении не отображается начисленный кэшбэк за покупки в категории супермаркеты за сентябрь месяц."),
    (1007, "call_center", "critical", "in_progress", "Мошенники оформили кредит на моё имя", "Безопасность", "Получил уведомление о выдаче потребительского кредита, который я не оформлял. Подозреваю мошеннические действия с моими персональными данными."),
    (1008, "web", "low", "resolved", "Как получить справку о движении средств", "Обслуживание", "Нужна справка о движении денежных средств по счёту за последние 12 месяцев для предоставления в налоговую инспекцию."),
    (1009, "mobile_app", "high", "open", "Не приходит код подтверждения по СМС", "Переводы", "При переводе денежных средств не приходит одноразовый код подтверждения на номер телефона, перевод не завершается."),
    (1010, "branch", "normal", "resolved", "Досрочное погашение ипотеки", "Кредиты", "Хочу оформить частичное досрочное погашение ипотечного кредита и пересчитать график платежей."),
    (1011, "call_center", "normal", "resolved", "Комиссия за обслуживание карты", "Карты", "Списана комиссия за годовое обслуживание дебетовой карты, хотя по условиям обслуживание бесплатное при обороте."),
    (1012, "atm", "normal", "resolved", "Банкомат не вернул карту", "Карты", "Банкомат в торговом центре не вернул карту после операции, прошу помочь в изъятии карты из устройства."),
    (1013, "mobile_app", "low", "resolved", "Как изменить лимит на переводы", "Мобильное приложение", "Хочу увеличить суточный лимит на переводы по карте через настройки мобильного приложения."),
    (1014, "web", "high", "in_progress", "Списание за подписку без согласия", "Безопасность", "Со счёта ежемесячно списывается плата за сервис, на который я не давал согласия, прошу вернуть средства."),
    (1015, "branch", "normal", "resolved", "Открытие накопительного счёта", "Вклады", "Хочу открыть накопительный счёт с возможностью пополнения и снятия без потери процентов."),
    (1016, "call_center", "high", "resolved", "Зарплата не поступила на карту", "Переводы", "Заработная плата за октябрь не поступила на зарплатную карту, работодатель утверждает, что платёж отправлен."),
    (1017, "mobile_app", "critical", "open", "Приложение показывает неверный баланс", "Мобильное приложение", "Баланс карты в мобильном приложении отличается от фактического остатка, операции отображаются с задержкой несколько часов."),
    (1018, "web", "normal", "resolved", "Автокредит: условия и ставка", "Кредиты", "Интересуют условия автокредита на новый автомобиль, процентная ставка и требования к заемщику."),
    (1019, "atm", "low", "resolved", "Банкомат не печатает чек", "Обслуживание", "Банкомат не печатает чек по операции снятия наличных, нужен документ для отчётности."),
    (1020, "call_center", "normal", "in_progress", "Перевод завис в обработке", "Переводы", "Внутренний перевод между счетами находится в статусе обработки более суток, деньги недоступны."),
    (1021, "mobile_app", "high", "resolved", "Сбой при оплате по QR-коду", "Мобильное приложение", "Оплата по QR-коду не проходит, приложение выдаёт ошибку сервиса при сканировании кода продавца."),
    (1022, "branch", "normal", "resolved", "Перевыпуск карты после утери", "Карты", "Утеряна дебетовая карта, прошу заблокировать и перевыпустить карту с новым номером."),
    (1023, "web", "low", "resolved", "Изменение паспортных данных", "Обслуживание", "Сменил паспорт, нужно обновить паспортные данные в системе банка для дальнейших операций."),
    (1024, "call_center", "critical", "in_progress", "Подозрительный звонок от имени банка", "Безопасность", "Поступил звонок от якобы сотрудника банка с просьбой назвать код из СМС и данные карты, прошу проверить."),
    (1025, "mobile_app", "normal", "resolved", "Не приходят push-уведомления", "Мобильное приложение", "Не приходят push-уведомления об операциях по карте, в настройках телефона уведомления разрешены."),
    (1026, "atm", "normal", "resolved", "Пополнение карты не отразилось на балансе", "Карты", "Внесение наличных на карту через банкомат не отразилось на балансе, чек сохранён."),
    (1027, "web", "high", "resolved", "Рефинансирование кредита другого банка", "Кредиты", "Хочу рефинансировать потребительский кредит другого банка, интересует ставка и срок."),
    (1028, "branch", "low", "resolved", "Закрытие неиспользуемого счёта", "Обслуживание", "Прошу закрыть неиспользуемый текущий счёт и перевести остаток денежных средств на карту."),
    (1029, "call_center", "normal", "resolved", "Проценты по вкладу не начислены", "Вклады", "По вкладу не начислены проценты за прошлый месяц, капитализация должна быть ежемесячной."),
    (1030, "mobile_app", "normal", "open", "Не открывается раздел инвестиции", "Мобильное приложение", "Раздел инвестиций в приложении не открывается, отображается пустой экран и ошибка загрузки."),
]


def byte_lengths() -> None:
    """Длины VARCHAR в БАЙТАХ — в Milvus max_length задаётся в байтах, не в символах."""
    print("[check] длины текстовых полей (байт UTF-8; кириллица = 2 байта на символ):")
    for name, pos in (("subject", 4), ("body", 6), ("category", 5)):
        print(f"    {name:<9} макс. {max(len(t[pos].encode('utf-8')) for t in TICKETS):>4} байт "
              f"(символов: {max(len(t[pos]) for t in TICKETS)})")


def create_collection() -> None:
    """Схема + индексы коллекции SupportTickets (идемпотентно: пересоздаём)."""
    if c.has_collection(COLL):
        c.drop_collection(COLL)

    s = c.create_schema(auto_id=True, enable_dynamic_field=False)
    s.add_field("ticket_id", DataType.INT64, is_primary=True)
    s.add_field("client_id", DataType.INT64)
    s.add_field("channel", DataType.VARCHAR, max_length=20)
    s.add_field("priority", DataType.VARCHAR, max_length=10)
    s.add_field("status", DataType.VARCHAR, max_length=15)
    s.add_field("created_at", DataType.VARCHAR, max_length=19)
    s.add_field("subject", DataType.VARCHAR, max_length=200)
    # enable_analyzer=True — по этому полю Milvus строит полнотекстовый индекс BM25
    s.add_field("body", DataType.VARCHAR, max_length=2000, enable_analyzer=True)
    # ВНИМАНИЕ: max_length в Milvus измеряется в БАЙТАХ, а кириллица в UTF-8 — 2 байта
    # на символ. "Мобильное приложение" = 20 символов = 39 байт, поэтому 30 мало.
    s.add_field("category", DataType.VARCHAR, max_length=60)
    s.add_field("body_vector", DataType.FLOAT_VECTOR, dim=DIM)     # dense: смысл текста
    s.add_field("body_sparse", DataType.SPARSE_FLOAT_VECTOR)       # sparse: слова
    # Function(BM25): Milvus сам строит разреженный вектор из body при вставке
    s.add_function(Function(name="bm25_body", function_type=FunctionType.BM25,
                            input_field_names=["body"], output_field_names=["body_sparse"]))

    idx = c.prepare_index_params()
    idx.add_index(field_name="body_vector", index_type="HNSW", metric_type="COSINE",
                  params={"M": 16, "efConstruction": 200})
    idx.add_index(field_name="body_sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25")
    for f in ("channel", "priority", "category", "status"):
        idx.add_index(field_name=f, index_type="INVERTED")
    c.create_collection(collection_name=COLL, schema=s, index_params=idx)
    print(f"[create] {COLL}: 12 полей, индексы HNSW/COSINE + SPARSE_INVERTED_INDEX/BM25 "
          f"+ 4 x INVERTED")


def show(title: str, hits) -> None:
    """Печать результатов поиска в читаемом виде."""
    print(f"\n  {title}")
    for i, h in enumerate(hits, 1):
        e = h["entity"]
        print(f"    {i}. {h['distance']:>7.4f} | {e['priority']:<8} {e['channel']:<11} "
              f"[{e['category']:<21}] {e['subject'][:48]}")


def main() -> int:
    print(f"модель эмбеддингов: {MODEL} ({API})")
    print(f"сервер Milvus: {c.get_server_version()}")

    create_collection()
    byte_lengths()

    # эмбеддинги считаем батчем с префиксом search_document (как для коллекций отчёта)
    vecs = embed([t[6] for t in TICKETS], "search_document: ")
    rows = []
    for (cid, ch, pr, st, subj, cat, body), v in zip(TICKETS, vecs):
        rows.append({
            "client_id": cid, "channel": ch, "priority": pr, "status": st,
            "created_at": f"2026-10-{cid - 1000:02d} 09:30:00",
            "subject": subj, "body": body, "category": cat, "body_vector": v,
        })
    print(f"[insert] {c.insert(COLL, rows).get('insert_count')} обращений "
          f"(body_sparse заполнен Milvus автоматически через Function BM25)")
    c.flush(collection_name=COLL)
    c.load_collection(COLL)
    print("[load] коллекция загружена в память")

    # --- 1) полнотекстовый поиск (BM25): ищем по словам, эмбеддинг не нужен ----
    r = c.search(collection_name=COLL, data=["перевод СБП получатель"],
                 anns_field="body_sparse", limit=3,
                 output_fields=["subject", "category", "channel", "priority"])
    show("1) ПОЛНОТЕКСТОВЫЙ поиск (BM25 по sparse): 'перевод СБП получатель'", r[0])

    # --- 2) семантический поиск (dense): ищем по смыслу ----------------------
    q = embed(["клиент не может снять деньги в банкомате"], "search_query: ")[0]
    r = c.search(collection_name=COLL, data=[q], anns_field="body_vector", limit=3,
                 search_params={"metric_type": "COSINE", "params": {"ef": 64}},
                 output_fields=["subject", "category", "channel", "priority"])
    show("2) СЕМАНТИЧЕСКИЙ поиск (dense, COSINE): 'не может снять деньги в банкомате'", r[0])

    # --- 3) гибридный поиск: dense + sparse, ранкер RRF ----------------------
    hq = "мошенники списание с карты без согласия"
    req_dense = AnnSearchRequest(data=[embed([hq], "search_query: ")[0]],
                                 anns_field="body_vector",
                                 param={"metric_type": "COSINE", "params": {"ef": 64}}, limit=5)
    req_sparse = AnnSearchRequest(data=[hq], anns_field="body_sparse", param={}, limit=5)
    r = c.hybrid_search(collection_name=COLL, reqs=[req_dense, req_sparse],
                        ranker=RRFRanker(60), limit=3,
                        output_fields=["subject", "category", "channel", "priority"])
    show("3) ГИБРИДНЫЙ поиск (dense+sparse, RRFRanker): "
         "'мошенники списание с карты без согласия'", r[0])

    # --- 4) гибридный поиск + фильтр по скалярным полям ---------------------
    # ВАЖНО: expr задаётся у КАЖДОГО AnnSearchRequest — hybrid_search склеивает
    # результаты нескольких подзапросов, поэтому фильтр на одном из них
    # не ограничит выдачу целиком (в ней останутся строки из другого подзапроса).
    expr = 'priority == "critical" and status == "open"'
    req_dense_f = AnnSearchRequest(data=[embed([hq], "search_query: ")[0]],
                                   anns_field="body_vector",
                                   param={"metric_type": "COSINE", "params": {"ef": 64}},
                                   limit=5, expr=expr)
    req_sparse_f = AnnSearchRequest(data=["карта приложение перевод"],
                                    anns_field="body_sparse", param={}, limit=5, expr=expr)
    r = c.hybrid_search(collection_name=COLL, reqs=[req_dense_f, req_sparse_f],
                        ranker=RRFRanker(60), limit=5,
                        output_fields=["subject", "category", "channel", "priority", "status"])
    show(f'4) ГИБРИДНЫЙ поиск + фильтр на ОБОИХ подзапросах ({expr})', r[0])

    # --- 5) агрегаты по каналам --------------------------------------------
    print("\n5) СТАТИСТИКА по каналам (query с count(*))")
    total = c.query(COLL, filter="", output_fields=["count(*)"])[0]["count(*)"]
    for ch in ("mobile_app", "call_center", "web", "branch", "atm"):
        n = c.query(COLL, filter=f'channel == "{ch}"', output_fields=["count(*)"])[0]["count(*)"]
        print(f"    {ch:<12} {n:>3}   ({n / total * 100:4.1f}%)")
    print(f"    {'ВСЕГО':<12} {total:>3}")
    crit = c.query(COLL, filter='priority == "critical"',
                   output_fields=["count(*)"])[0]["count(*)"]
    print(f"    критичных обращений: {crit}")

    if not KEEP:
        print(f"\n[cleanup] коллекция {COLL} удалена (флаг --keep оставляет её в Milvus)")
        c.drop_collection(COLL)
    else:
        print(f"\n[keep] коллекция {COLL} оставлена в Milvus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())