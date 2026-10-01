# Milvus + Attu (Windows + Docker Desktop)

Поднять **Milvus 3.0** и **Attu 3.0** одной командой через Docker Desktop и работать с документами Word:
залить документ, искать (по словам и по смыслу), выгрузить обратно.

> **Пошаговая инструкция «для чайника» → [INSTRUCTION.md](INSTRUCTION.md)**
> (запуск, вход в Attu, оба варианта заливки, поиск, AI-агент, выгрузка, эталонные экраны).

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
| `scripts/vectorize_docx.py` | `.docx` → коллекция Milvus с эмбеддингами (локальная модель или OpenAI-совместимый API) |
| `scripts/docx_to_milvus_bm25.py` | `.docx` → коллекция Milvus BM25 (full-text, **без модели**) |
| `scripts/docx_to_jsonl.py` | `.docx` → JSONL (для ручного Import в Attu) |
| `scripts/milvus_export.py` | Обратная выгрузка: коллекция Milvus → `.txt` / `.docx` / `.jsonl` |
| `scripts/requirements-vectorize.txt` | Python-зависимости скриптов |
| `INSTRUCTION.md` | Полная инструкция для новичка |

## Два способа поиска

| Способ | Модель | Ищет | Заливка |
|--------|--------|------|---------|
| **BM25 (full-text)** | не нужна | по словам | `docx_to_milvus_bm25.py` |
| **Семантический** | нужна (эмбеддинги) | по смыслу | `vectorize_docx.py --embedder api` |

```powershell
python -m pip install -r .\scripts\requirements-vectorize.txt

# 1) без модели — поиск по словам
python .\scripts\docx_to_milvus_bm25.py --file "D:\FILE_WORD\moskva.docx" --collection moskva_ft `
  --user root --password MilvusDemo123 --recreate

# 2) с моделью — поиск по смыслу (пример: LM Studio локально, 0 токенов)
python .\scripts\vectorize_docx.py --file "D:\FILE_WORD\moskva.docx" --collection moskva_sem `
  --user root --password MilvusDemo123 --embedder api `
  --api-base http://127.0.0.1:1234/v1 --api-key "<ТОКЕН LM STUDIO>" `
  --api-model text-embedding-nomic-embed-text-v1.5 --batch 64 --recreate
```

> ⚠️ Для семантики нужен сервер с **`/v1/embeddings`** (LM Studio, Ollama, TEI, OpenAI…).
> Чат-ключ (`/chat/completions`) для поиска не подойдёт — он только для AI-агента.

## Обратная выгрузка (Milvus → файл)

```powershell
python .\scripts\milvus_export.py --collection moskva_sem --out moskva_back.docx --format docx `
  --user root --password MilvusDemo123
```
Возвращает **текст** чанков в порядке `chunk_index`. Исходная вёрстка Word (картинки, стили,
таблицы) не сохраняется. В Attu то же можно сделать через меню коллекции → **Export Data** (JSONL/Parquet).

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

## Legacy (Kubernetes/Helm — не требуется)

В репозитории остались файлы для K8s-варианта (`chart/`, `values/`,
`scripts/install-milvus-attu.ps1`, `scripts/share-*.ps1`). Для запуска через Docker Desktop
они **не нужны**.