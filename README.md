# Milvus + Attu (Windows + Docker Desktop)

Поднять **Milvus 3.0** и **Attu 3.0** одной командой через Docker Desktop — это стенд для
отчёта по векторной базе данных в предметной области «Банковские данные»:
коллекции продуктов и транзакций, семантический поиск, категоризация, выявление аномалий,
RBAC и ресурсные группы, эксперименты по индексам и метрикам.

> **Пошаговая инструкция → [INSTRUCTION.md](INSTRUCTION.md)**
> (запуск стенда, вход в Attu, создание коллекций, RBAC, прогон шагов и экспериментов отчёта).

Kubernetes и GitLab **не нужны** — только Docker Desktop.

## Быстрый старт

```powershell
git clone https://github.com/one6way/milvus-attu-doc.git
cd milvus-attu-doc
docker compose up -d          # etcd + MinIO + Milvus + Attu
docker compose ps             # ждать healthy у milvus-standalone (~1-2 мин)
```

- **Attu (веб-UI):** http://127.0.0.1:13000 — вход `admin` / `AttuDemo123!`
- **Connect к Milvus:** host `milvus`, port `19530`, user `root`, password `MilvusDemo123`
- **Milvus (SDK):** `127.0.0.1:19530` — `MilvusClient(uri="http://127.0.0.1:19530", token="root:MilvusDemo123")`

## Что внутри

| Путь | Назначение |
|------|------------|
| `docker-compose.yml` | Milvus 3.0 (standalone) + Attu 3.0 + etcd + MinIO |
| `docker/milvus-user.yaml` | Override-конфиг Milvus: авторизация + `mq.type=woodpecker` |
| `scripts/` | Скрипты стенда и экспериментов (полный перечень — Приложение Г отчёта) |
| `scripts/steps/` | Скрипты-шаги главы 3 (подтверждения разделов отчёта) |
| `scripts/benchmark_result.json` | Результаты замеров для §3.6 (получены `scripts/A7_benchmark.py`) |
| `INSTRUCTION.md` | Пошаговая инструкция: запуск стенда и прогон всех шагов отчёта |

## Банковский стенд из отчёта

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pymilvus requests

.\.venv\Scripts\python.exe scripts\create_banking_collections.py --embedder api `
  --api-base http://127.0.0.1:1234/v1 --api-key "<токен LM Studio>" `
  --api-model text-embedding-nomic-embed-text-v1.5 --recreate

.\.venv\Scripts\python.exe scripts\A6_rbac.py
.\.venv\Scripts\python.exe scripts\steps\S09_search_products.py
.\.venv\Scripts\python.exe scripts\steps\S10_categorization.py
.\.venv\Scripts\python.exe scripts\steps\S11_anomalies.py
```

Коллекции: `BankingProducts`, `Transactions` (векторы dim=768) и справочники
`Currencies`, `Clients`, `Accounts`, `Cards`. Метрика — `COSINE`, индекс — `HNSW`.

## Управление

```powershell
docker compose stop        # пауза (данные сохраняются)
docker compose down        # удалить контейнеры (данные в volumes остаются)
docker compose down -v     # удалить всё вместе с данными (чистый старт)
```

## Требования

- **Windows 10/11**, **Docker Desktop** (запущен, Linux containers)
- **Python 3.10+** — для скриптов заливки/поиска
- Свободные порты: **13000, 19530, 9000, 9001**
- Интернет на первую загрузку образов (~1.3 ГБ)

## Безопасность

Пароли в репозитории **демонстрационные** (`MilvusDemo123`, `AttuDemo123!`) и лежат в git.
Перед публикацией портов наружу смените `defaultRootPassword` в `docker/milvus-user.yaml`
и `ATTU_ADMIN_PASSWORD` в `docker-compose.yml`.