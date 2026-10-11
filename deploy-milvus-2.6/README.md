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
