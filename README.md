# Milvus + Attu: стенд для работы по банковской предметной области

Репозиторий содержит **только материалы практической части**: конфигурацию стенда,
скрипты и инструкцию проверяющего. Отчёт (`ОТЧЁТ_Milvus_банковские_данные_акт.docx`)
в репозиторий не входит.

Стенд поднимается одной командой через Docker Desktop — Kubernetes и GitLab не нужны:

**Milvus v3.0.1 (standalone) + Attu v3.0.1 + etcd + MinIO** — коллекции банковских
продуктов, транзакций и обращений клиентов, семантический и полнотекстовый поиск,
гибридный поиск, категоризация, выявление аномалий, RBAC и ресурсные группы,
эксперименты по индексам и метрикам.

> **Пошаговая инструкция проверяющего → [INSTRUCTION.md](INSTRUCTION.md)**
> Каждый шаг описан по схеме «зачем → что делаем → ожидаемый результат»,
> есть чек-лист (§14) и таблица эталонных значений (§15).

## Быстрый старт

```powershell
git clone https://github.com/one6way/milvus-attu-doc.git
cd milvus-attu-doc

docker compose up -d          # etcd + MinIO + Milvus + Attu
docker compose ps             # ждать healthy у milvus-standalone (1-2 мин)
curl http://127.0.0.1:9091/healthz   # ответ: OK

py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install pymilvus==3.0.2 requests numpy
```

- **Attu (веб-UI):** <http://127.0.0.1:13000> — вход `admin` / `AttuDemo123!`
- **Connect к Milvus:** host `milvus`, port `19530`, user `root`, password `MilvusDemo123`
- **Milvus (SDK):** `MilvusClient(uri="http://127.0.0.1:19530", token="root:MilvusDemo123")`

## Что внутри

| Путь | Назначение |
|------|------------|
| `docker-compose.yml` | Milvus v3.0.1 (standalone) + Attu v3.0.1 + etcd + MinIO |
| `docker/milvus-user.yaml` | override-конфиг Milvus: включённая авторизация, `mq.type=woodpecker` |
| `scripts/create_banking_collections.py` | создание шести коллекций, генерация данных, расчёт эмбеддингов |
| `scripts/A6_rbac.py`, `scripts/A6b_rbac_check.py` | настройка RBAC и проверка разграничения доступа |
| `scripts/A7_benchmark.py` | эксперименты §3.6: efConstruction, ef, индексы, фильтры, метрики |
| `scripts/embed_server_local.py` | локальный сервис эмбеддингов (если нет LM Studio) |
| `scripts/restore_rg.py` | откат ресурсных групп после эксперимента с переносом узла |
| `scripts/milvus_export.py`, `scripts/probe_api.py`, `scripts/probe_rbac.py`, `scripts/selfcheck.py`, `scripts/A3_A4_A5_embed_search_anomaly.py` | вспомогательные проверки API и сквозной сценарий |
| `scripts/steps/S06…S17*.py` | точечные проверки разделов главы 3 |
| `scripts/steps/S18_support_tickets.py` | **дополнительный шаг**: коллекция обращений `SupportTickets`, BM25 и гибридный поиск |
| `scripts/benchmark_result.json` | эталонные замеры §3.6 (его читает `S15_metrics.py`) |
| `INSTRUCTION.md` | пошаговая инструкция: запуск стенда, данные, RBAC, шаги и эксперименты |

## Банковский стенд

Скрипты создают шесть коллекций (метрика `COSINE`, векторные поля dim=768):

| Коллекция | Содержимое | Индексы |
|---|---|---|
| `BankingProducts` | 30 банковских продуктов (вектор `description_vector`) | HNSW, INVERTED, STL_SORT |
| `Transactions` | 30 проводок (вектор `purpose_vector`) | HNSW, INVERTED, STL_SORT |
| `Currencies`, `Clients`, `Accounts`, `Cards` | 10 / 10 / 30 / 20 справочных записей | FLAT (тех. поле `_tech_vector`) |

Дополнительно `S18_support_tickets.py` создаёт коллекцию **`SupportTickets`** —
30 обращений клиентов в поддержку (карты, переводы, кредиты, вклады, безопасность,
мобильное приложение) — и демонстрирует **полнотекстовый (BM25)** и
**гибридный (dense + sparse, `RRFRanker`)** поиск: `body_sparse` заполняет сам Milvus
через `Function(BM25)`.

```powershell
.\.venv\Scripts\python.exe scripts\create_banking_collections.py --embedder api `
  --api-base http://127.0.0.1:1234/v1 --api-key "<токен LM Studio>" --recreate
.\.venv\Scripts\python.exe scripts\steps\S18_support_tickets.py --keep
.\.venv\Scripts\python.exe scripts\A6_rbac.py
.\.venv\Scripts\python.exe scripts\steps\S09_search_products.py
.\.venv\Scripts\python.exe scripts\steps\S10_categorization.py
.\.venv\Scripts\python.exe scripts\steps\S11_anomalies.py
```

## Сервис эмбеддингов: два варианта

1. **LM Studio** (как в отчёте): модель `text-embedding-nomic-embed-text-v1.5`,
   сервер на порту `1234`, при *Require Authentication* — токен `sk-lm-…`.
   Пошаговая установка, загрузка модели и запуск сервера — §5 в
   [INSTRUCTION.md](INSTRUCTION.md), подразделы **А.1–А.7** (есть и CLI:
   `lms ls` / `lms load` / `lms server status`).
2. **Локальный сервер** (без отдельного приложения, проверенный резервный путь):

```powershell
.\.venv\Scripts\python.exe -m pip install sentence-transformers
.\.venv\Scripts\python.exe scripts\embed_server_local.py --port 8091 --prefix=
$env:EMBED_API = 'http://127.0.0.1:8091/v1/embeddings'
```

`--prefix=` (пусто) обязателен: скрипты отчёта сами добавляют `search_document:` /
`search_query:`. Подробнее — §5 в [INSTRUCTION.md](INSTRUCTION.md).

## Управление

```powershell
docker compose stop        # пауза (данные сохраняются)
docker compose up -d       # запуск снова
docker compose down        # удалить контейнеры (данные в томах остаются)
docker compose down -v     # удалить всё вместе с данными (чистый старт)
```

## Требования

- **Windows 10/11**, **Docker Desktop** (запущен, Linux containers, не менее 6 ГБ памяти)
- **Python 3.11** (достаточно 3.10+) и `pymilvus==3.0.2`, `requests`, `numpy`
- Свободные порты: **13000, 19530, 9091, 9000, 9001** и порт сервиса эмбеддингов
  (**1234** или **8091**)
- Интернет на первую загрузку образов (около 1,3 ГБ) и модели эмбеддингов (около 2 ГБ)

## Безопасность

Пароли в репозитории **демонстрационные** (`MilvusDemo123`, `AttuDemo123!`) и лежат в git.
Перед публикацией портов наружу смените `defaultRootPassword` в `docker/milvus-user.yaml`
и `ATTU_ADMIN_PASSWORD` в `docker-compose.yml`.