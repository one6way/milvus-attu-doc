# -*- coding: utf-8 -*-
"""Шаг отчёта §3.6.7: оценка качества категоризации транзакций (Precision/Recall/F1).

Методика: 5 эталонных категорий с кодами MCC, для каждой — эталонное описание
(прототип). Классификация назначения платежа — по ближайшему соседу среди
векторов прототипов (косинусная близость); категория = MCC ближайшего прототипа.
Тестовый набор: 30 размеченных вручную формулировок (по 6 на категорию).

Модель эмбеддингов: text-embedding-nomic-embed-text-v1.5 (LM Studio).

Запуск:  .venv\\Scripts\\python.exe scripts\\steps\\S16_categorization_eval.py
"""
import json
import urllib.request

API = "http://127.0.0.1:1234/v1/embeddings"
KEY = "sk-lm-STX4hpuF:WyBJuG9KKXe9MCMuTz6s"
MODEL = "text-embedding-nomic-embed-text-v1.5"


def embed(texts, prefix):
    body = json.dumps({"model": MODEL, "input": [prefix + t for t in texts]}).encode()
    req = urllib.request.Request(API, data=body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + KEY})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = sorted(json.loads(r.read())["data"], key=lambda x: x["index"])
    return [[float(v) for v in x["embedding"]] for x in data]


# категория -> (MCC, прототип, тестовые формулировки)
CATS = {
    "Продукты и супермаркеты": ("5411", "Оплата продуктов и супермаркетов, покупка еды", [
        "Покупка продуктов в магазине «Пятёрочка»",
        "Закуп еды в супермаркете",
        "Оплата продуктовой корзины картой",
        "Продукты на неделю в Ашане",
        "Покупка хлеба и молока в магазине",
        "Оплата продуктов на кассе",
    ]),
    "Коммунальные услуги": ("4900", "Платёж за коммунальные услуги и ЖКХ", [
        "Оплата электроэнергии за квартиру",
        "Квартплата за месяц",
        "Платёж за воду и отопление",
        "Оплата услуг ЖКХ по квитанции",
        "Взнос за содержание жилья",
        "Перевод за коммунальные платежи",
    ]),
    "Транспорт и такси": ("4121", "Оплата транспорта, такси и проезда", [
        "Оплата поездки на такси",
        "Пополнение карты Тройка",
        "Покупка билета на метро",
        "Оплата проезда в автобусе",
        "Оплата каршеринга",
        "Платёж за такси Яндекс",
    ]),
    "Рестораны и кафе": ("5812", "Оплата в ресторанах, кафе и фастфуде", [
        "Счёт в ресторане на ужин",
        "Оплата кофе в кофейне",
        "Бизнес-ланч в столовой",
        "Оплата доставки еды из ресторана",
        "Счёт за пиццу",
        "Оплата ужина в кафе",
    ]),
    "Аптеки": ("5912", "Покупка лекарств в аптеке", [
        "Покупка лекарств",
        "Оплата рецепта в аптеке",
        "Покупка витаминов в аптеке",
        "Аптечный чек за медикаменты",
        "Оплата лекарств по рецепту",
        "Покупка медикаментов",
    ]),
}

print(f"модель эмбеддингов: {MODEL} (LM Studio)\n")

names = list(CATS)
proto_vec = embed([CATS[n][1] for n in names], "search_document: ")

def cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb)

tp = {n: 0 for n in names}
fp = {n: 0 for n in names}
fn = {n: 0 for n in names}
total = correct = 0

for true in names:
    phrases = CATS[true][2]
    vecs = embed(phrases, "search_query: ")
    print(f"=== {true} (MCC {CATS[true][0]}) ===")
    for text, v in zip(phrases, vecs):
        sims = [cos(v, p) for p in proto_vec]
        pred = names[max(range(len(names)), key=lambda i: sims[i])]
        total += 1
        if pred == true:
            tp[true] += 1
            correct += 1
            mark = "ok"
        else:
            fp[pred] += 1
            fn[true] += 1
            mark = f"ОШИБКА -> {pred}"
        print(f"  cos={max(sims):.4f}  {mark:<28} {text}")
    print()

print("Категория\tMCC\tPrecision\tRecall\tF1")
sp = sr = sf = 0.0
for n in names:
    p = tp[n] / (tp[n] + fp[n]) if tp[n] + fp[n] else 0.0
    r = tp[n] / (tp[n] + fn[n]) if tp[n] + fn[n] else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    sp += p
    sr += r
    sf += f
    print(f"{n}\t{CATS[n][0]}\t{p:.2f}\t{r:.2f}\t{f:.2f}")
k = len(names)
print(f"Среднее (macro)\t—\t{sp/k:.2f}\t{sr/k:.2f}\t{sf/k:.2f}")
print(f"\nИТОГ: корректно классифицировано {correct} из {total} формулировок "
      f"(accuracy = {correct/total:.2f}).")
