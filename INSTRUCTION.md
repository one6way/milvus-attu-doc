# Milvus + Attu — инструкция: стенд для отчёта (Windows + Docker Desktop)

Пошагово: от чистой машины до работающего поиска по банковским данным — те же шаги,
которые подтверждают разделы главы 3 отчёта.

## 0. Что понадобится

- **Windows 10/11** и **Docker Desktop** (запущен, Linux containers)
- **Python 3.10+** — для скриптов стенда
- **Сервис эмбеддингов** с OpenAI-совместимым `/v1/embeddings` (LM Studio, TEI, Ollama…)
- Свободные порты: **13000** (Attu), **19530** (Milvus gRPC), **9000/9001** (MinIO), **9091** (healthz)
- Интернет на первую загрузку образов (~1.3 ГБ)

Kubernetes и GitLab не нужны — только Docker Desktop.

## 1. Получить репозиторий

```powershell
git clone https://github.com/one6way/milvus-attu-doc.git
cd milvus-attu-doc
```

## 2. Поднять Milvus и Attu

```powershell
docker compose up -d
docker compose ps                    # ждать healthy у milvus-standalone (1-2 мин)
curl http://127.0.0.1:9091/healthz   # ответ: OK
```

## 3. Зайти в Attu

Откройте <http://127.0.0.1:13000>, вход `admin` / `AttuDemo123!`.
Затем **Connect**: host `milvus`, port `19530`, user `root`, password `MilvusDemo123`.

## 4. Python-окружение

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pymilvus requests
```

## 5. Сервис эмбеддингов (LM Studio)

1. Загрузите модель **`text-embedding-nomic-embed-text-v1.5`** (размерность 768).
2. Вкладка **Developer/Server** → **Start Server**, порт **1234**.
3. Проверка: `curl http://127.0.0.1:1234/v1/models`.
4. Если включён **Require Authentication** — скопируйте токен `sk-lm-…` и передавайте его
   через `--api-key` либо через переменную окружения `EMBED_KEY`
   (скрипты читают `EMBED_API` / `EMBED_KEY`; для Milvus — `MILVUS_URI` / `MILVUS_TOKEN`).

## 6. Создать коллекции и залить данные

```powershell
.\.venv\Scripts\python.exe scripts\create_banking_collections.py --embedder api `
  --api-base http://127.0.0.1:1234/v1 --api-key "<токен LM Studio>" `
  --api-model text-embedding-nomic-embed-text-v1.5 --recreate
```

Создаются: `BankingProducts`, `Transactions` (векторы dim=768) и справочники
`Currencies`, `Clients`, `Accounts`, `Cards`. Метрика `COSINE`, индекс `HNSW`.

## 7. Роли, пользователи, ресурсные группы

```powershell
.\.venv\Scripts\python.exe scripts\A6_rbac.py                       # роли, права, группы
.\.venv\Scripts\python.exe scripts\steps\S12_rbac_setup.py          # чистая настройка RBAC
.\.venv\Scripts\python.exe scripts\A6b_rbac_check.py                # проверка доступа
.\.venv\Scripts\python.exe scripts\steps\S14_resource_groups.py     # ресурсные группы
```

## 8. Шаги, подтверждающие главу 3

Все запускаются из корня репозитория:

| Раздел отчёта | Команда | Что показывает |
|---|---|---|
| §3.2.2-3.2.3 | `scripts\steps\S06_schema.py` | схема 6 коллекций: поля, типы, индексы |
| §3.3.1 | `scripts\steps\S17_embedding_vector.py` | значения вектора `description_vector` |
| §3.3.3 | `scripts\steps\S08_counts.py` | число строк в каждой коллекции |
| §3.4.1 | `scripts\steps\S09_search_products.py` | семантический поиск продуктов |
| §3.4.2 | `scripts\steps\S10_categorization.py` | категоризация по назначению платежа |
| §3.4.3 | `scripts\steps\S11_anomalies.py` | аномалии: расстояние до центроида (θ = μ − 2σ) |

```powershell
.\.venv\Scripts\python.exe scripts\steps\S06_schema.py
.\.venv\Scripts\python.exe scripts\steps\S17_embedding_vector.py
.\.venv\Scripts\python.exe scripts\steps\S08_counts.py
.\.venv\Scripts\python.exe scripts\steps\S09_search_products.py
.\.venv\Scripts\python.exe scripts\steps\S10_categorization.py
.\.venv\Scripts\python.exe scripts\steps\S11_anomalies.py
```

## 9. Эксперименты (§3.6)

```powershell
.\.venv\Scripts\python.exe scripts\A7_benchmark.py --n 50000 --queries 100 --runs 5
.\.venv\Scripts\python.exe scripts\steps\S15_metrics.py             # таблицы 3.1-3.5
.\.venv\Scripts\python.exe scripts\steps\S16_categorization_eval.py # Precision/Recall/F1
```

Замеры сохраняются в `scripts/benchmark_result.json` — именно его читает `S15_metrics.py`.

## 10. Остановить / удалить

```powershell
docker compose stop      # пауза (данные сохраняются)
docker compose down      # удалить контейнеры (данные в volumes остаются)
docker compose down -v   # удалить всё вместе с данными (чистый старт)
```

## 11. Если что-то не так

| Симптом | Что делать |
|---|---|
| Attu не открывается | `docker compose ps` — ждать `healthy`; проверить порт 13000 |
| `UNAUTHENTICATED` в Attu | в Connect: host `milvus`, user `root`, password `MilvusDemo123`; удалить соединение без пароля |
| Скрипт: `Connection refused` | Milvus ещё не поднялся либо порт 19530 занят |
| Эмбеддинги: `401/403` | включён Require Authentication — задайте `EMBED_KEY` (`sk-lm-…`) |
| Эмбеддинги: `connection refused` | LM Studio не запущен либо другой порт (`EMBED_API`) |
| Порт 14000 занят | измените левую часть `ports` в `docker-compose.yml`, например `"14000:3000"` |
| Нужны логи | `docker compose logs milvus-standalone --tail 100` |

## 12. Шпаргалка

```powershell
# поднять стенд
docker compose up -d
# браузер: http://127.0.0.1:13000  (админ Attu: admin / AttuDemo123!)
#          Connect: milvus / 19530 / root / MilvusDemo123

# данные и проверки
.\.venv\Scripts\python.exe scripts\create_banking_collections.py --embedder api `
  --api-base http://127.0.0.1:1234/v1 --api-key "<токен LM Studio>" --recreate
.\.venv\Scripts\python.exe scripts\A6_rbac.py
.\.venv\Scripts\python.exe scripts\steps\S09_search_products.py
.\.venv\Scripts\python.exe scripts\steps\S10_categorization.py
.\.venv\Scripts\python.exe scripts\steps\S11_anomalies.py

# остановить
docker compose down
```

> Пароли в репозитории **демонстрационные** (`MilvusDemo123`, `AttuDemo123!`).
> Перед публикацией портов наружу смените `defaultRootPassword` в `docker/milvus-user.yaml`
> и `ATTU_ADMIN_PASSWORD` в `docker-compose.yml`.