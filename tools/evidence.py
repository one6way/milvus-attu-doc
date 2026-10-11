# -*- coding: utf-8 -*-
"""Карта «доказательств» для отчёта: раздел -> команда / вывод / скриншот."""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EVID = {
    "3.1.2": {
        "desc": "Проверка выполнения (развёртывание из репозитория)",
        "cmd": ["docker compose up -d"],
        "files": [("состав стека: docker compose ps", "report/evidence/E01_ps.txt"),
                  ("проверка состояния", "report/evidence/E02_healthz.txt")],
        "shots": [("screens/S01_cluster_overview.png", "Attu: версия сервера, режим Standalone")],
    },
    "3.1.3": {
        "desc": "Проверка выполнения (веб-интерфейс)",
        "cmd": [],
        "files": [],
        "shots": [("screens/S00_login.png", "Вход в Attu"),
                  ("screens/S02_collections.png", "Список коллекций в Attu")],
    },
    "3.1.4": {
        "desc": "Проверка выполнения (авторизация)",
        "cmd": [],
        "codes": [("docker/milvus-user.yaml", "docker/milvus-user.yaml")],
        "files": [("проверка входа под root", "report/evidence/E04_auth.txt")],
        "shots": [],
    },
    "3.2.1": {
        "desc": "Проверка выполнения (подключение и версия сервера)",
        "cmd": [".venv\\Scripts\\python.exe -c \"...MilvusClient(...).list_collections()\""],
        "files": [("вывод", "report/evidence/E03_connect.txt")],
        "shots": [],
    },
    "3.2.2": {
        "desc": "Проверка выполнения (схема коллекций)",
        "cmd": [".venv\\Scripts\\python.exe report\\steps\\S06_schema.py"],
        "scripts": ["scripts/create_banking_collections.py", "report/steps/S06_schema.py"],
        "files": [("вывод", "report/evidence/E06_schema.txt")],
        "shots": [("screens/S03_schema_products.png", "Attu: схема BankingProducts"),
                  ("screens/S13_schema_transactions.png", "Attu: схема Transactions")],
    },
    "3.2.3": {
        "desc": "Проверка выполнения (индексы)",
        "cmd": [],
        "files": [],
        "shots": [("screens/S15_index_products.png", "Attu: индексы BankingProducts"),
                  ("screens/S20_index_transactions.png", "Attu: индексы Transactions")],
    },
    "3.3.1": {
        "desc": "Проверка выполнения (модель эмбеддингов E5)",
        "cmd": [".venv\\Scripts\\python.exe scripts\\create_banking_collections.py --embedder e5 ..."],
        "files": [("загрузка модели и векторизация", "report/evidence/E05_create_collections.txt")],
        "shots": [("screens/S09_embedding_e5_test.png", "Attu: проверка провайдера эмбеддингов"),
                  ("screens/S10_embedding_providers.png", "Attu: настроенные провайдеры")],
    },
    "3.3.2": {
        "desc": "Проверка выполнения (объём синтетических данных)",
        "cmd": [".venv\\Scripts\\python.exe report\\steps\\S08_counts.py"],
        "files": [("вывод", "report/evidence/E08_counts.txt")],
        "shots": [],
    },
    "3.3.3": {
        "desc": "Проверка выполнения (данные загружены)",
        "cmd": [],
        "files": [],
        "shots": [("screens/S04_data_products.png", "Attu: данные коллекции BankingProducts")],
    },
    "3.4.1": {
        "desc": "Проверка выполнения (семантический поиск продуктов)",
        "cmd": [".venv\\Scripts\\python.exe report\\steps\\S09_search_products.py"],
        "scripts": ["report/steps/S09_search_products.py"],
        "files": [("вывод", "report/evidence/E09_search_products.txt")],
        "shots": [("screens/S05_search_products.png", "Attu: результаты поиска продуктов")],
    },
    "3.4.2": {
        "desc": "Проверка выполнения (категоризация транзакций)",
        "cmd": [".venv\\Scripts\\python.exe report\\steps\\S10_categorization.py"],
        "scripts": ["report/steps/S10_categorization.py"],
        "files": [("вывод", "report/evidence/E10_categorization.txt")],
        "shots": [("screens/S16_search_transactions.png", "Attu: поиск похожих назначений платежей")],
    },
    "3.4.3": {
        "desc": "Проверка выполнения (выявление аномалий, θ = μ − 2σ)",
        "cmd": [".venv\\Scripts\\python.exe report\\steps\\S11_anomalies.py"],
        "scripts": ["report/steps/S11_anomalies.py"],
        "files": [("вывод", "report/evidence/E11_anomalies.txt")],
        "shots": [("screens/S25_anomaly_lowsim.png", "Attu: запрос с низким сходством"),
                  ("screens/S22_search_tx_anomalies.png", "Вывод скрипта по 3.4.1–3.4.3")],
    },
    "3.5.1": {
        "desc": "Проверка выполнения (роли и пользователи)",
        "cmd": [".venv\\Scripts\\python.exe report\\steps\\S12_rbac_setup.py"],
        "scripts": ["listings_script/A6_rbac.py", "report/steps/S12_rbac_setup.py"],
        "files": [("вывод", "report/evidence/E12_rbac_setup.txt")],
        "shots": [("screens/S06_users.png", "Attu: пользователи и их роли"),
                  ("screens/S07_roles.png", "Attu: роли (analyst +7 прав, viewer +2)")],
    },
    "3.5.2": {
        "desc": "Проверка выполнения (разграничение доступа)",
        "cmd": [".venv\\Scripts\\python.exe listings_script\\A6b_rbac_check.py"],
        "scripts": ["listings_script/A6b_rbac_check.py"],
        "files": [("вывод", "report/evidence/E13_rbac_check.txt")],
        "shots": [("screens/S23_rbac_verification.png", "Итог проверки доступа")],
    },
    "3.5.3": {
        "desc": "Проверка выполнения (ресурсные группы)",
        "cmd": [".venv\\Scripts\\python.exe report\\steps\\S14_resource_groups.py"],
        "scripts": ["report/steps/S14_resource_groups.py"],
        "files": [("вывод", "report/evidence/E14_resource_groups.txt")],
        "shots": [("screens/S24_resource_groups.png", "Attu: ресурсные группы")],
    },
    "3.6.0": {
        "desc": "Проверка выполнения (результаты экспериментов)",
        "cmd": [".venv\\Scripts\\python.exe report\\steps\\S15_metrics.py"],
        "scripts": ["listings_script/A7_benchmark.py", "report/steps/S15_metrics.py"],
        "files": [("вывод", "report/evidence/E15_metrics.txt")],
        "shots": [("screens/S08_metrics.png", "Сводные таблицы экспериментов")],
    },
}


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def _read(p):
    fp = os.path.join(ROOT, p.replace("/", os.sep))
    if not os.path.exists(fp):
        return None
    return io.open(fp, encoding="utf-8", errors="replace").read().rstrip()


_N = 100000


def _seq():
    """Уникальный номер для маркера картинки (в разных разделах бывают одинаковые имена файлов)."""
    global _N
    _N += 1
    return _N


def evidence_blocks(spec):
    out = [{"t": "p", "text": spec["desc"]}]
    for c in spec.get("cmd", []):
        out.append({"t": "code", "text": "$ " + c})
    for s in spec.get("scripts", []):
        out.append({"t": "p", "text": "Скрипт: " + s})
    for name, path in spec.get("codes", []):
        txt = _read(path)
        if txt:
            out.append({"t": "p", "text": "Листинг " + name})
            out.append({"t": "code", "text": txt})
    for title, path in spec.get("files", []):
        txt = _read(path)
        if txt:
            out.append({"t": "p", "text": "Вывод: " + title})
            out.append({"t": "code", "text": txt})
    for path, cap in spec.get("shots", []):
        fp = os.path.join(ROOT, path.replace("/", os.sep))
        if os.path.exists(fp):
            w, h = png_size(fp)
            marker = f"EVFIGMARK::{_seq()}::{os.path.basename(fp)}"
            out.append({"t": "fig", "file": fp, "caption": cap, "w": w, "h": h,
                        "marker": marker})
    return out


def inject_evidence(blocks):
    """Вставить блок «доказательств» в конец соответствующего раздела."""
    heads = [(i, b["num"]) for i, b in enumerate(blocks)
             if b["t"] in ("h1", "h2", "h3") and b.get("num")]
    result = list(blocks)
    for num in [n for _, n in reversed(heads) if n in EVID]:
        start = next(i for i, b in enumerate(result)
                     if b["t"] in ("h1", "h2", "h3") and b.get("num") == num)
        level = num.count(".")
        end = len(result)
        for j in range(start + 1, len(result)):
            b = result[j]
            if (b["t"] in ("h1", "h2", "h3") and b.get("num")
                    and b["num"].count(".") <= level):
                end = j
                break
        result[end:end] = evidence_blocks(EVID[num])
    return result


