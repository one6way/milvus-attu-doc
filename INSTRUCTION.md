# Milvus + Attu — инструкция для чайника (Windows + Docker Desktop)

Просто и по шагам: поднять базу, залить документ Word, искать. Без Kubernetes.

---

## 0. Что понадобится

- **Windows 10/11** и **Docker Desktop** (запущен, режим **Linux containers**).
- **Git** (или скачай репо ZIP с GitHub вручную).
- **Python 3.10+** (нужен только для скриптов заливки/поиска).
- Свободные порты: **13000**, **19530**, **9000**, **9001**.
- Интернет на первую загрузку образов (~1.3 ГБ).

Проверить, что Docker готов:
```powershell
docker version
docker compose version
```

---

## 1. Скачать репозиторий

```powershell
git clone https://github.com/one6way/milvus-attu-doc.git
cd milvus-attu-doc
```
> Если git нет — открой https://github.com/one6way/milvus-attu-doc → **Code → Download ZIP**, распакуй и перейди в папку.

---

## 2. Поднять Milvus + Attu

Из папки репо (там, где лежит `docker-compose.yml`):
```powershell
docker compose up -d
```
Подожди 1–2 минуты (Milvus инициализируется). Проверка готовности:
```powershell
docker compose ps
```
Нужно увидеть `milvus-standalone` со статусом **healthy** (и `milvus-minio`, `milvus-etcd` — healthy, `attu` — Up).

Если `milvus-standalone` долго не healthy — смотри логи:
```powershell
docker compose logs -f milvus
```
(выход — `Ctrl+C`).

---

## 3. Зайти в Attu

1. Открой в браузере: **http://127.0.0.1:13000**
2. Войди в Attu (это логин самого интерфейса):
   - **Логин:** `admin`
   - **Пароль:** `AttuDemo123!`
3. Соединение с Milvus уже создано автоматически. Нажми **Connect** (или выбери соединение `milvus:19530`). Если спросит вручную:
   - **Host:** `milvus`  ← важно: НЕ `127.0.0.1`
   - **Port:** `19530`
   - **User:** `root`
   - **Password:** `MilvusDemo123`

✅ Готово — ты внутри. Слева список коллекций.

> **Логины/пароли (запомни):**
> | Где | Логин | Пароль |
> |-----|-------|--------|
> | Вход в Attu | `admin` | `AttuDemo123!` |
> | Подключение к Milvus | `root` | `MilvusDemo123` |

---

## 4. Установить Python-зависимости (для скриптов)

```powershell
python -m pip install -r .\scripts\requirements-vectorize.txt
```
Это поставит `python-docx`, `pymilvus`, `requests` — хватит для заливки **без модели**.
(Модель — отдельно, см. Кейс B.)

---

## 5. Залить документ Word — 2 кейса

Есть два разных способа поиска, и заливка под них отличается:

| Кейс | Модель | Поиск ищет | Быстро? |
|------|--------|-----------|---------|
| **A. Full-text (BM25)** | не нужна | по словам | да |
| **B. Семантический** | нужна | по смыслу | надо ставить модель |

### Кейс A — БЕЗ модели (BM25, по словам)

Одной командой (создаёт коллекцию и заливает текст):
```powershell
python .\scripts\docx_to_milvus_bm25.py --file "D:\FILE_WORD\file.docx" --collection docs_ft `
  --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123 --recreate --demo
```
Что произойдёт: текст нарежется на чанки → создастся коллекция `docs_ft` → вставится текст →
(с `--demo`) сразу покажется пример поиска.

> `--collection docs_ft` — имя коллекции (любое). `--recreate` — пересоздать заново.
> Без `--demo` просто зальёт и всё.

Проверь в Attu: обнови список — появится коллекция `docs_ft`. Открой её → увидишь строки (текст).

### Кейс B — С моделью (семантический, по смыслу)

Сначала поставь модель (один раз). Два варианта — выбери один:

**B1. Локальная модель (офлайн, 0 токенов, ~5 ГБ загрузка):**
```powershell
python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
python -m pip install "sentence-transformers>=3.0.0"
```
Затем залей документ (модель bge-m3 скачается при первом запуске):
```powershell
python .\scripts\vectorize_docx.py --file "D:\FILE_WORD\file.docx" --collection docs_sem `
  --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123
```

**B2. Внешний OpenAI-совместимый endpoint (ничего тяжёлого ставить не надо):**
```powershell
python .\scripts\vectorize_docx.py --file "D:\FILE_WORD\file.docx" --collection docs_sem `
  --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123 `
  --embedder api --api-base https://<твой-хост>/v1 --api-key <ключ> --api-model text-embedding-3-small
```
Здесь создаётся коллекция `docs_sem` с полем `vector` (эмбеддинги).

> Коллекция из Кейса A (`docs_ft`) и из Кейса B (`docs_sem`) — **разные**.
> Это нормально: разные типы поиска живут в разных коллекциях.

---

## 6. Как искать — 2 варианта

### Вариант 1 — по словам (без модели), коллекция `docs_ft`

**В Attu:**
1. Открой коллекцию `docs_ft`.
2. Нажми **Search** (или поле поиска сверху).
3. Выбери режим **full-text / BM25** (sparse-вектор).
4. Введи запрос **словами**, например: `автоматизация развёртывания`.
5. Run — увидишь подходящие куски текста и score.

**Из Python (проверено):**
```powershell
python .\scripts\docx_to_milvus_bm25.py --file "D:\FILE_WORD\file.docx" --collection docs_ft `
  --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123 --demo `
  --query "автоматизация развёртывания контейнеров"
```
> BM25 ищет **совпадения слов**. Синонимы не находит (нужен Кейс B).

### Вариант 2 — по смыслу (с моделью), коллекция `docs_sem`

Поиск из Python (вектор запроса считается той же моделью, что и данные):
```python
from pymilvus import MilvusClient
c = MilvusClient(uri="http://127.0.0.1:19530", token="root:MilvusDemo123")
# для B1 (локальная модель):
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("BAAI/bge-m3")
qvec = m.encode(["как масштабировать приложение"], normalize_embeddings=True)[0].tolist()
hits = c.search("docs_sem", data=[qvec], anns_field="vector", limit=3, output_fields=["content"])
for h in hits[0]:
    print(h["distance"], h["entity"]["content"][:100])
```

**В Attu (AI-поиск):** открой коллекцию → панель **AI/Search**. Чтобы она строила вектор запроса,
в **Settings → Embeddings** укажи тот же провайдер (OpenAI-совместимый `baseUrl` + `/v1/embeddings`)
и **ту же модель**, что строила векторы. Иначе результаты будут мимо.

> Вариант 2 ищет **по смыслу**: запрос «масштабирование нагрузки» найдёт текст про
> «scale up при росте трафика», даже если слов нет.

---

## 7. Остановить / удалить

```powershell
docker compose stop        # пауза (данные сохраняются)
docker compose down        # удалить контейнеры (данные в volumes остаются)
docker compose down -v     # удалить ВСЁ вместе с данными (чистый старт)
```

---

## 8. Если что-то не так

| Симптом | Что делать |
|---------|-----------|
| `Connection Unavailable ... UNAUTHENTICATED` в Attu | В Connect проверь: host `milvus`, user `root`, password `MilvusDemo123`. Удали старое соединение без пароля и подключись снова. |
| Порт занят (`13000`/`19530`) | В `docker-compose.yml` поменяй левую часть в `ports` (напр. `"14000:3000"`), затем `docker compose up -d`. |
| `milvus-standalone` не healthy | Дай Docker больше памяти (Settings → Resources, ≥ 6 ГБ) и подожди 2–3 мин. Смотри `docker compose logs -f milvus`. |
| `ERROR: нужен python-docx` | `python -m pip install -r .\scripts\requirements-vectorize.txt` |
| `ERROR: --embedder offline требует sentence-transformers` | Поставь модель (Кейс B1) или используй `--embedder api` (B2). |
| Torch падает на GPU (RTX 50xx) | Нужен CUDA-12.8: `pip install torch --index-url https://download.pytorch.org/whl/cu128` |
| Не понимаю, нужна ли модель | Поиск по словам → **не нужна** (Кейс A). Поиск по смыслу → **нужна** (Кейс B). |

---

## 9. Шпаргалка (всё в 6 строк)

```powershell
git clone https://github.com/one6way/milvus-attu-doc.git; cd milvus-attu-doc
docker compose up -d                      # поднять
# браузер: http://127.0.0.1:13000  (admin / AttuDemo123!  -> Connect milvus/19530 root/MilvusDemo123)
python -m pip install -r .\scripts\requirements-vectorize.txt
# без модели (по словам):   python .\scripts\docx_to_milvus_bm25.py --file "D:\FILE_WORD\file.docx" --collection docs_ft --user root --password MilvusDemo123 --recreate --demo
# с моделью (по смыслу):    python .\scripts\vectorize_docx.py --file "D:\FILE_WORD\file.docx" --collection docs_sem --user root --password MilvusDemo123
```