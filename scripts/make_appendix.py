"""Сборка ПРИЛОЖЕНИЯ А (листинги программ) из реально запускавшихся скриптов.

Листинги НЕ пишутся руками: файл PRILOZHENIE_A.md генерируется из тех самых скриптов
папки verify/, которые дали результаты главы 3 (логи — verify/*.log).

Запуск:  python .\\verify\\make_appendix.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent          # корень репозитория milvus-attu
OUT = HERE.parent / "PRILOZHENIE_A.md"

SECTIONS = [
    ("А.1. Скрипт развёртывания Milvus Standalone",
     "Развёртывание выполняется через docker compose (Milvus + Attu + etcd + MinIO). "
     "Ниже — фактически использованные файлы; авторизация включается ключом "
     "defaultRootPassword ВНУТРИ common.security (см. правку к разделу 3.1.4).",
     [(ROOT / "docker-compose.yml", "yaml"),
      (ROOT / "docker" / "milvus-user.yaml", "yaml")]),

    ("А.2. Скрипт создания коллекций и индексов",
     "Создание всех шести коллекций: BankingProducts, Transactions, Clients, Currencies, "
     "Accounts, Cards. Учтены платформенные требования: техническое векторное поле _tech_vector "
     "для справочников и nullable=True для полей, допускающих NULL.",
     [(HERE / "check_v2_code.py", "python")]),

    ("А.3. Генератор синтетических банковских данных",
     "Тот же файл реализует пункты А.3–А.5: список банковских продуктов и назначений платежей, "
     "функции генерации эмбеддингов, семантический поиск, категоризацию и выявление аномалий. "
     "Полный листинг приведён здесь один раз, чтобы не дублировать его в А.4 и А.5.",
     [(HERE / "probe_embed.py", "python")]),

    ("А.4. Скрипт генерации эмбеддингов (с префиксами E5)",
     "Реализация находится в листинге А.3 (функции embed_passage / embed_query, модель "
     "intfloat/multilingual-e5-base, normalize_embeddings=True). Модель даёт вектор размерности 768 "
     "с единичной нормой: shape = (768,), ||v|| = 1.000000 (замер — verify/probe_embed.log).",
     [(HERE / "probe_embed.py", "python")]),

    ("А.5. Скрипты семантического поиска, категоризации, выявления аномалий",
     "Реализация находится в листинге А.3 (разделы 3.4.1, 3.4.2, 3.4.3: поиск продуктов с "
     "скалярным фильтром, поиск похожих назначений, центроид и калибровка порога theta = mu - 2*sigma).",
     [(HERE / "probe_embed.py", "python")]),

    ("А.6. Скрипт настройки RBAC и ресурсных групп",
     "Создание ролей (кроме встроенной admin), выдача прав, пользователи, проверка разграничения "
     "доступа реальными данными, ресурсные группы (привязка к коллекции) и корректный откат.",
     [(HERE / "probe_rbac.py", "python"),
      (HERE / "restore_rg.py", "python")]),

    ("А.7. Скрипт проведения экспериментов и сбора метрик",
     "Замеры для таблиц 3.1–3.4 и 3.6.5–3.6.6: влияние efConstruction и ef, сравнение индексов "
     "FLAT / IVF_FLAT / IVF_SQ8 / HNSW, влияние скалярной фильтрации, сравнение метрик L2 / IP / COSINE. "
     "Эталон — точный поиск FLAT, Recall@k = |A_approx ∩ A_exact| / k.",
     [(HERE / "benchmark.py", "python")]),
]

EXTRA = [
    ("Общие утилиты харнесса (подключение, логирование, проверки)",
     [(HERE / "common.py", "python")]),
    ("Самопроверка стенда (три ожидаемые ошибки платформы)",
     [(HERE / "selfcheck.py", "python")]),
]



def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path.name)


def render_block(title: str, note: str, files: list[tuple[Path, str]], included: set) -> list[str]:
    lines = [f"## {title}", "", note, ""]
    for path, lang in files:
        if not path.exists():
            lines += [f"Файл `{rel(path)}` не найден — листинг пропущен.", ""]
            continue
        if path in included:
            lines += [f"Листинг файла `{path.name}` приведён выше (в том разделе, где он "
                      "включён впервые) — здесь не дублируется.", ""]
            continue
        included.add(path)
        text = path.read_text(encoding="utf-8").rstrip()
        lines += [f"**Файл: `{rel(path)}`** ({len(text.splitlines())} строк)", "",
                  f"```{lang}", text, "```", ""]
    return lines


def main() -> int:
    out: list[str] = [
        "# ПРИЛОЖЕНИЕ А. ЛИСТИНГИ ПРОГРАММ",
        "",
        "Информационная система на основе векторной базы данных Milvus "
        "для предметной области «Банковские данные»",
        "",
        "Листинги **не набраны вручную**: файл собран скриптом `verify/make_appendix.py` из тех самых "
        "исходников папки `verify/`, которые запускались на стенде и дали результаты главы 3. "
        "К каждому листингу прилагается лог прогона (`verify/*.log`), а машинные результаты замеров "
        "сохранены в `verify/benchmark_result.json`.",
        "",
        "Условия прогона: Windows 11 + Docker Desktop; Milvus Standalone **v3.0.1** "
        "(образ milvusdb/milvus:v3.0.1) в режиме docker compose, etcd v3.5.25 и MinIO "
        "RELEASE.2024-12-18T13-15-44Z отдельными контейнерами; Python 3.11.9; pymilvus **3.0.2**; "
        "sentence-transformers 6.1.0; torch 2.14.1 (CPU); авторизация включена, "
        "пользователь root/MilvusDemo123. Те же сценарии дополнительно сверены на Milvus v2.6.11.",
        "",
        "==================================================================================",
        "",
    ]

    included: set[Path] = set()
    for title, note, files in SECTIONS:
        out += render_block(title, note, files, included)

    out += ["### Вспомогательные листинги", ""]
    for title, files in EXTRA:
        out += render_block(title, "Приведён для воспроизводимости замеров и проверок.", files, included)

    result_json = HERE / "benchmark_result.json"
    out += ["### Результаты замеров (машинный вывод скрипта А.7)", ""]
    if result_json.exists():
        out += ["**Файл: `verify/benchmark_result.json`**", "", "```json",
                result_json.read_text(encoding="utf-8").rstrip(), "```", ""]
    else:
        out += ["Файл `verify/benchmark_result.json` появится после запуска "
                "`python .\\verify\\benchmark.py`.", ""]

    logs = sorted(HERE.glob("*.log"))
    if logs:
        out += ["### Логи прогонов листингов", ""]
        for log in logs:
            out += [f"* `verify/{log.name}` — {log.stat().st_size} байт;"]
        out += [""]

    text = "\n".join(out).rstrip() + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\r\n")
    print(f"собрано: {OUT} ({len(text.splitlines())} строк, {len(text.encode('utf-8'))} байт)")
    print(f"включено листингов: {len(included)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
