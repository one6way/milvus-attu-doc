# Milvus 2.6.11 + Attu 2.6.5 (Docker Desktop)

Версия **Milvus 2.6.11** — та, что использована в отчёте для проверок (v2.6.11).
Разворачивается отдельно от основного стека `../docker-compose.yml` (там Milvus 3.0.1).

## Состав

| Сервис | Образ | Порт |
|--------|-------|------|
| `milvus` | `milvusdb/milvus:v2.6.11` | 19530 (gRPC), 9091 (healthz/metrics) |
| `attu` | `zilliz/attu:v2.6.5` | 13000 → 3000 |
| `etcd` | `quay.io/coreos/etcd:v3.5.25` | — |
| `minio` | `milvusdb/minio:RELEASE.2024-12-18T13-15-44Z` | 9000, 9001 |

> MinIO берётся из зеркала `milvusdb/minio`: официальный тег `minio/minio:RELEASE.2024-05-28…`
> из upstream-рецепта Milvus больше не доступен в Docker Hub.

## Запуск

```powershell
cd deploy-milvus-2.6
docker compose up -d
docker compose ps          # ждать healthy у milvus-standalone (~1–2 мин, start_period 90s)
```

## Доступ

- **Attu:** http://127.0.0.1:13000
  Форма Connect: **Milvus Address** = `milvus:19530`, Authentication → username/password:
  **`root`** / **`MilvusDemo123`**.
  (Attu 2.x не подхватывает соединение из env — адрес вводится в форме.)
- **Milvus (SDK):** `127.0.0.1:19530`, user `root`, password `MilvusDemo123`.
- Проверка: `http://127.0.0.1:9091/healthz` → `OK`.

Проверено: `utility.get_server_version()` = **2.6.11**, Deploy Mode = **STANDALONE**;
авторизация включена (неверный пароль → `UNAUTHENTICATED`).

```python
from pymilvus import MilvusClient
c = MilvusClient(uri="http://127.0.0.1:19530", token="root:MilvusDemo123")
print(c.list_collections())
```

## Авторизация

`user.yaml` монтируется в `/milvus/configs/user.yaml`. В Milvus 2.6 ключ
`defaultRootPassword` находится **внутри** `common.security`:

```yaml
common:
  security:
    authorizationEnabled: true
    defaultRootPassword: MilvusDemo123
```

## Остановить / переключиться обратно на 3.0

```powershell
# стоп 2.6 (тома сохраняются)
cd deploy-milvus-2.6; docker compose down

# вернуть основной стек Milvus 3.0.1 + Attu 3.0.1
cd ..; docker compose up -d
```

> Порты у обоих стеков одинаковые (19530/13000/9000/9001) — **одновременно они работать не могут**.
> Данные 2.6 лежат в `deploy-milvus-2.6/volumes/` и не пересекаются с томами 3.0.

---

# Загрузка банковской системы из отчёта в Milvus 2.6.11 (пошагово)

Скриншоты — в `../screens/report26/` (`R01`…`R05`).

### Шаг 0. Поднять стенд 2.6.11
```powershell
cd deploy-milvus-2.6
docker compose up -d
docker compose ps      # milvus-standalone должен стать healthy
```
Проверка: `curl http://127.0.0.1:9091/healthz` → `OK`.

### Шаг 1. Python-окружение
Нужен интерпретатор с `pymilvus` и `sentence-transformers` (для эмбеддингов E5).
В этом репозитории он уже есть в venv:
```
d:\milvus-attu\.venv\Scripts\python.exe
```
(если venv активирован не был — вызываем полным путём, иначе берётся глобальный Python без этих библиотек).

### Шаг 2. Создать 6 коллекций + данные (эмбеддинги E5, dim=768)
```powershell
cd d:\milvus-attu
.\.venv\Scripts\python.exe .\scripts\create_banking_collections.py --embedder e5 `
  --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123 --recreate
```
Создаёт: `BankingProducts` (30), `Transactions` (30), `Currencies` (10), `Clients` (10),
`Accounts` (30), `Cards` (20). Индексы — как в отчёте: HNSW/COSINE, INVERTED, STL_SORT;
у справочников тех. поле `_tech_vector` (dim=2).

### Шаг 3. RBAC и ресурсные группы
```powershell
$env:MILVUS_HOST='127.0.0.1'; $env:MILVUS_PORT='19530'
$env:MILVUS_USER='root';      $env:MILVUS_PASSWORD='MilvusDemo123'
.\.venv\Scripts\python.exe .\listings_script\A6_rbac.py
```
Создаёт роли `analyst` (+7 прав) и `viewer` (+2 права), пользователей
`admin_user` / `analyst_user` / `viewer_user`, ресурсные группы
`rg_high_priority` (→ Transactions) и `rg_low_priority` (→ BankingProducts).

### Шаг 4. Проверить разграничение доступа
```powershell
.\.venv\Scripts\python.exe .\listings_script\A6b_rbac_check.py
# viewer_user: BankingProducts.search=ALLOW, Transactions.search=DENY, Transactions.insert=DENY
# analyst_user: Transactions.search/insert=ALLOW, create_collection=DENY
# ИТОГ: все проверки совпали
```

### Шаг 5. Посмотреть в Attu
http://127.0.0.1:13000 → Connect: Address `milvus:19530`, username/password `root` / `MilvusDemo123`:
- `R01_collections.png` — 6 коллекций, MILVUS VERSION 2.6.11, STANDALONE
- `R02_db_default.png` — БД `default` со списком коллекций и счётчиками
- `R03_products.png` — схема `BankingProducts` (nullable-поля, INVERTED, STL_SORT)
- `R04_users.png` — Users: root/admin, admin_user/admin, analyst_user/analyst, viewer_user/viewer
- `R05_roles.png` — Roles: admin, analyst, public, viewer

> В Attu 2.6.5 разделы доступны по адресам `#/users`, `#/roles`, `#/system`.

### Итоговое состояние (проверено)
```
BankingProducts 30 | Transactions 31 | Currencies 10 | Clients 10 | Accounts 30 | Cards 20
roles: admin, analyst, public, viewer
users: root, admin_user, analyst_user, viewer_user
resource groups: __default_resource_group, rg_high_priority, rg_low_priority
```

