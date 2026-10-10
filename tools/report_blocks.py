# -*- coding: utf-8 -*-
"""Препроцессор отчёта: otchet.txt -> blocks.json (для генерации .docx через docx-js)."""
import io, json, re, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "milvusattugorobec", "otchet.txt")
SHOTS = os.path.join(ROOT, "screens")
OUT = os.path.join(ROOT, "tools", "blocks.json")

H1 = re.compile(r"^(\d+)\.\s+(\S.*)$")
H2 = re.compile(r"^(\d+\.\d+)\.\s+(\S.*)$")
H3 = re.compile(r"^(\d+\.\d+\.\d+)\.\s+(\S.*)$")
CAPTION = re.compile(r"^(Таблица|Рисунок)\s+\d")
CAPS_TITLE = re.compile(r"^(ВВЕДЕНИЕ|ЗАКЛЮЧЕНИЕ|СОДЕРЖАНИЕ|АННОТАЦИЯ|РЕФЕРАТ|"
                        r"СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ|ПРИЛОЖЕНИЕ\s+[А-ЯA-Z].*)$")
CODEMARK = {"python", "bash", "yaml", "json", "powershell", "shell", "text", "sql", "js", "javascript"}

# какие скриншоты вставлять после раздела (по номеру раздела)
FIG = {
    "2.1":  [("S01_cluster_overview.png", "Milvus Standalone v3.0.1 в Attu: режим развёртывания и узлы")],
    "2.3":  [("S02_collections.png", "Список созданных коллекций банковской системы")],
    "2.3.1": [("S03_schema_products.png", "Схема коллекции BankingProducts (вектор description_vector, dim=768)")],
    "2.3.2": [("S14_schema_clients.png", "Схема коллекции Clients (техническое поле _tech_vector)")],
    "2.3.3": [("S17_schema_currencies.png", "Схема коллекции Currencies")],
    "2.3.4": [("S18_schema_accounts.png", "Схема коллекции Accounts")],
    "2.3.5": [("S19_schema_cards.png", "Схема коллекции Cards")],
    "2.3.6": [("S13_schema_transactions.png", "Схема коллекции Transactions (purpose_vector, dim=768)")],
    "2.4":  [("S15_index_products.png", "Индексы BankingProducts: HNSW/COSINE, INVERTED, STL_SORT"),
             ("S20_index_transactions.png", "Индексы Transactions")],
    "2.7":  [("S06_users.png", "Разграничение доступа: пользователи admin_user/analyst_user/viewer_user и их роли"),
             ("S07_roles.png", "Роли: analyst (+7 прав) и viewer (+2 права)"),
             ("S21_role_privileges.png", "Детализация прав ролей и ресурсные группы")],
    "2.8":  [("S24_resource_groups.png", "Ресурсные группы: default, rg_high_priority, rg_low_priority")],
    "2.9.1": [("S05_search_products.png", "Семантический поиск продуктов в Attu (модель E5)")],
    "3.1":  [("S00_login.png", "Вход в веб-интерфейс Attu")],
    "3.3":  [("S04_data_products.png", "Загруженные данные коллекции BankingProducts"),
             ("S09_embedding_e5_test.png", "Проверка подключения провайдера эмбеддингов E5"),
             ("S10_embedding_providers.png", "Настроенные провайдеры эмбеддингов")],
    "3.4.2": [("S16_search_transactions.png", "Поиск похожих назначений платежей (Transactions)")],
    "3.4.3": [("S25_anomaly_lowsim.png", "Сценарий аномалии: запрос не по теме, низкие значения сходства"),
              ("S22_search_tx_anomalies.png", "Вывод скрипта: поиск, категоризация, аномалии (θ = μ−2σ)")],
    "3.5":  [("S23_rbac_verification.png", "Проверка разграничения доступа реальными данными")],
    "3.6":  [("S08_metrics.png", "Результаты экспериментов: efConstruction, ef, индексы, фильтры, метрики")],
}

CODECHARS = set("=(){}[]<>;")

def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    w = int.from_bytes(head[16:20], "big")
    h = int.from_bytes(head[20:24], "big")
    return w, h

def is_prose(s):
    t = s.strip()
    if not t:
        return False
    if t.startswith(("#", "//", "-", "*")):
        return False
    if any(c in CODECHARS for c in t):
        return False
    words = t.split()
    return t.endswith((".", "!", "?", ":")) and len(words) >= 4


def parse():
    raw = io.open(SRC, encoding="utf-8").read().replace("\r\n", "\n")
    lines = raw.split("\n")

    start = 0
    for i, ln in enumerate(lines):
        if ln.strip().startswith("Информационная система на основе векторной базы данных Milvus"):
            start = i
            break
    lines = lines[start:]

    blocks = []
    code = []
    in_code = False

    def flush_code():
        nonlocal code, in_code
        if code:
            blocks.append({"t": "code", "text": "\n".join(code).rstrip()})
            code = []
        in_code = False

    def add_figs(num):
        for fn, cap in FIG.get(num, []):
            p = os.path.join(SHOTS, fn)
            if os.path.exists(p):
                w, h = png_size(p)
                blocks.append({"t": "fig", "file": p, "caption": cap, "w": w, "h": h})

    for ln in lines:
        s = ln.rstrip()
        st = s.strip()

        m = H3.match(st) or H2.match(st) or H1.match(st)
        if m:
            flush_code()
            num = m.group(1)
            title = m.group(2)
            level = num.count(".") + 1
            blocks.append({"t": "h%d" % level, "num": num, "text": f"{num}. {title}"})
            add_figs(num)
            continue
        if CAPS_TITLE.match(st):
            flush_code()
            blocks.append({"t": "h1", "num": "", "text": st})
            continue
        if st.lower() in CODEMARK:
            flush_code()
            in_code = True
            continue
        if not st:
            if in_code:
                code.append("")
            continue
        if in_code:
            if is_prose(st):
                flush_code()
                blocks.append({"t": "p", "text": st})
            else:
                code.append(s)
            continue
        if CAPTION.match(st):
            blocks.append({"t": "caption", "text": st})
            continue
        blocks.append({"t": "p", "text": st})

    flush_code()
    return blocks


if __name__ == "__main__":
    b = parse()
    io.open(OUT, "w", encoding="utf-8").write(json.dumps(b, ensure_ascii=False))
    from collections import Counter
    print("blocks:", len(b), Counter(x["t"] for x in b))
    print("figs:", sum(1 for x in b if x["t"] == "fig"))
    print("sample:", json.dumps(b[:2], ensure_ascii=False)[:250])
