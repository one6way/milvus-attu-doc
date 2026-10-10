# listings_script — листинги Приложения А (со скриншотами)

Скрипты из отчёта (Приложение А) + скриншоты их работы в Attu. Всё прогнано на живом
стенде Milvus 3.0.1 + Attu 3.0.1 (Docker Desktop, без Kubernetes).

## Соответствие: раздел отчёта → файл → скриншот

| Раздел | Файл(ы) | Что делает | Скриншот |
|--------|---------|-----------|----------|
| **А.1** Развёртывание | `A1_docker-compose.yml`, `A1_milvus-user.yaml` | Milvus 3.0 standalone + Attu (docker compose), авторизация root | `screens/S01_cluster_overview.png` |
| **А.2** Коллекции и индексы | `A2_A3_collections_and_data.py` | создаёт 6 коллекций + индексы (HNSW/COSINE, INVERTED, STL_SORT) | `S02_collections.png`, `S03_schema_products.png`, `S13_schema_transactions.png`, `S14_schema_clients.png`, `S15_index_products.png` |
| **А.3** Генератор данных | `A2_A3_collections_and_data.py` | 30 продуктов, 30 проводок, 10 валют, 10 клиентов, 30 счетов, 20 карт | `screens/S04_data_products.png` |
| **А.4** Эмбеддинги E5 | `A2_A3_collections_and_data.py --embedder e5`, `e5_embed_server.py` | `intfloat/multilingual-e5-base`, префиксы `passage:`/`query:`, dim=768, normalize | `S09_embedding_e5_test.png`, `S10_embedding_providers.png` |
| **А.5** Поиск / категоризация / аномалии | `A3_A4_A5_embed_search_anomaly.py` | 3.4.1 поиск продуктов с фильтром; 3.4.2 похожие назначения; 3.4.3 аномалии по центроиду (θ = μ−2σ) | `S05_search_products.png`, `S16_search_transactions.png` |
| **А.6** RBAC и ресурсные группы | `A6_rbac.py`, `A6b_rbac_check.py` (+ `probe_rbac.py`) | роли `analyst`/`viewer`, юзеры `admin_user`/`analyst_user`/`viewer_user`, группы `rg_high_priority`/`rg_low_priority`; проверка доступа реальными данными | **`S06_users.png`**, **`S07_roles.png`**, `S21_role_privileges.png`, `S23_rbac_verification.png` |
| **А.7** Эксперименты и метрики | `A7_benchmark.py` | efConstruction, ef, индексы, фильтры, метрики (N=50000) | `screens/S08_metrics.png` |
| Вспомогательное | `common.py`, `selfcheck.py`, `probe_api.py`, `probe_fix.py`, `restore_rg.py`, `make_appendix.py` | харнесс, самопроверка, RBAC-проба, откат ресурсной группы | — |

## Как запускать

```powershell
# окружение стенда
$env:MILVUS_HOST='127.0.0.1'; $env:MILVUS_PORT='19530'
$env:MILVUS_USER='root';      $env:MILVUS_PASSWORD='MilvusDemo123'

# А.2 + А.3: коллекции + синтетические данные на E5 (как в отчёте, dim=768)
python .\listings_script\A2_A3_collections_and_data.py --embedder e5 --recreate `
  --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123

# А.4: локальный OpenAI-совместимый сервер E5 для поиска из UI Attu
python .\listings_script\e5_embed_server.py --port 8091
#   Attu: Settings → Embedding → Add Provider → Custom:
#     Base URL = http://host.docker.internal:8091, Model = intfloat/multilingual-e5-base, Dimension = 768

# А.6: RBAC (роли analyst/viewer, пользователи, ресурсные группы)
python .\listings_script\A6_rbac.py
```

## RBAC — результат (совпадает с отчётом, раздел 2.7)

| Пользователь | Роль |
|--------------|------|
| `admin_user` | `admin` (встроенная) |
| `analyst_user` | `analyst` (+7 прав: Transactions S/Q/I/D/U, BankingProducts S/Q) |
| `viewer_user` | `viewer` (+2 права: BankingProducts Search/Query) |

Ресурсные группы: `rg_high_priority` → `Transactions`, `rg_low_priority` → `BankingProducts`.

> Скриншоты: `screens/S06_users.png` (пользователи), `screens/S07_roles.png` (роли с числом прав).

## Модель эмбеддингов (важно)

Отчёт (§3.3.1) использует **`intfloat/multilingual-e5-base`**: dim=768, префиксы
`passage: ` (документы) и `query: ` (запросы), `normalize_embeddings=True`.

- Заливка «как в отчёте»: `A2_A3_collections_and_data.py --embedder e5`
  (модель берётся из кэша HF, работает на CPU).
- Чтобы поиск **из UI Attu** считал вектор той же моделью, поднят локальный
  OpenAI-совместимый сервер `e5_embed_server.py` (порт 8091, префикс `query: `)
  и подключён в Attu: **Settings → Embedding → Add Provider → Custom**
  (`Base URL = http://host.docker.internal:8091`, `Model = intfloat/multilingual-e5-base`, `Dimension = 768`).
  Скрины: `S09_embedding_e5_test.png` (Test Connection), `S10_embedding_providers.png` (список провайдеров).

> Ранее использовался `text-embedding-nomic-embed-text-v1.5` из LM Studio (та же размерность 768,
> но префиксы `search_document:`/`search_query:` и другое векторное пространство) —
> для соответствия отчёту заменён на E5.

## Скриншоты (папка `screens/`)

| Файл | Раздел отчёта | Что на скрине |
|------|---------------|----------------|
| `S00_login.png` | 3.1 | вход в Attu |
| `S01_cluster_overview.png` | 2.1 | Milvus Standalone, версия 3.0.1, узлы |
| `S02_collections.png` | 2.3 | список 6 банковских коллекций |
| `S03_schema_products.png` | 2.3.1 | схема BankingProducts (vector dim=768) |
| `S04_data_products.png` | 3.3 | данные BankingProducts (30 записей) |
| `S05_search_products.png` | 2.9.1 / 3.4.1 | семантический поиск продуктов (E5) |
| `S06_users.png` | 2.7 / 3.5 | пользователи (admin_user/admin, analyst_user/analyst, viewer_user/viewer) |
| `S07_roles.png` | 2.7 / 3.5 | роли (analyst +7 прав, viewer +2 права) |
| `S08_metrics.png` | 3.6 / А.7 | таблицы метрик (efConstruction, ef, индексы, фильтры, метрики) |
| `S09_embedding_e5_test.png` | 3.3 | Test Connection провайдера E5 → success |
| `S10_embedding_providers.png` | 3.3 | список провайдеров эмбеддингов |
| `S13_schema_transactions.png` | 2.3.6 | схема Transactions (purpose_vector dim=768) |
| `S14_schema_clients.png` | 2.3.2 | схема Clients (+ `_tech_vector`) |
| `S15_index_products.png` | 2.4 | индексы BankingProducts (HNSW, INVERTED, STL_SORT) |
| `S16_search_transactions.png` | 3.4.2 | поиск похожих транзакций (E5) |
| `S17_schema_currencies.png` | 2.3.3 | схема Currencies (`_tech_vector`) |
| `S18_schema_accounts.png` | 2.3.4 | схема Accounts |
| `S19_schema_cards.png` | 2.3.5 | схема Cards |
| `S20_index_transactions.png` | 2.4 | индексы Transactions |
| `S21_role_privileges.png` | 2.7 / 3.5 | права ролей analyst (+7) и viewer (+2), пользователи, ресурсные группы |
| `S22_search_tx_anomalies.png` | 3.4.1/3.4.2/3.4.3 | вывод скрипта: поиск продуктов, похожие платежи, аномалии (θ = μ−2σ) |
| `S23_rbac_verification.png` | 3.5.2 | проверка доступа: viewer/analyst — разрешено/запрещено (все совпало) |
