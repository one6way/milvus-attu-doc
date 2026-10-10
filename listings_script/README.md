# listings_script — листинги Приложения А (со скриншотами)

Скрипты из отчёта (Приложение А) + скриншоты их работы в Attu. Всё прогнано на живом
стенде Milvus 3.0.1 + Attu 3.0.1 (Docker Desktop, без Kubernetes).

## Соответствие: раздел отчёта → файл → скриншот

| Раздел | Файл(ы) | Что делает | Скриншот |
|--------|---------|-----------|----------|
| **А.1** Развёртывание | `A1_docker-compose.yml`, `A1_milvus-user.yaml` | Milvus 3.0 standalone + Attu (docker compose), авторизация root | `screens/S01_cluster_overview.png` |
| **А.2** Коллекции и индексы | `A2_A3_collections_and_data.py` | создаёт 6 коллекций + индексы (HNSW/COSINE, INVERTED, STL_SORT) | `screens/S02_collections.png`, `S03_schema_products.png` |
| **А.3** Генератор данных | `A2_A3_collections_and_data.py` | 30 продуктов, 30 проводок, 10 валют, 10 клиентов, 30 счетов, 20 карт | `screens/S04_data_products.png` |
| **А.4** Эмбеддинги (E5) | `A3_A4_A5_embed_search_anomaly.py` | `embed_passage`/`embed_query` (префиксы `passage:`/`query:`, dim=768, normalize) | `screens/S03_schema_products.png` (вектор dim=768), `S05_search_products.png` |
| **А.5** Поиск / категоризация / аномалии | `A3_A4_A5_embed_search_anomaly.py` | 3.4.1 поиск продуктов с фильтром; 3.4.2 похожие назначения; 3.4.3 аномалии по центроиду (θ = μ−2σ) | `screens/S05_search_products.png` |
| **А.6** RBAC и ресурсные группы | `A6_rbac.py` (+ `probe_rbac.py`) | роли `analyst`/`viewer`, юзеры `admin_user`/`analyst_user`/`viewer_user`, группы `rg_high_priority`/`rg_low_priority` | **`screens/S06_users.png`**, **`screens/S07_roles.png`** |
| **А.7** Эксперименты и метрики | `A7_benchmark.py` | efConstruction, ef, индексы, фильтры, метрики (N=50000) | `screens/S08_metrics.png` |
| Вспомогательное | `common.py`, `selfcheck.py`, `probe_api.py`, `probe_fix.py`, `restore_rg.py`, `make_appendix.py` | харнесс, самопроверка, RBAC-проба, откат ресурсной группы | — |

## Как запускать

```powershell
# окружение стенда
$env:MILVUS_HOST='127.0.0.1'; $env:MILVUS_PORT='19530'
$env:MILVUS_USER='root';      $env:MILVUS_PASSWORD='MilvusDemo123'

# А.2 + А.3: коллекции + синтетические данные (эмбеддинги через LM Studio, dim=768)
python .\listings_script\A2_A3_collections_and_data.py `
  --api-base http://127.0.0.1:1234/v1 --api-key "<токен LM Studio>" `
  --api-model text-embedding-nomic-embed-text-v1.5 --recreate

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
