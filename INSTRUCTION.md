# Milvus + Attu — инструкция для чайника (Windows + Docker Desktop)

Просто и по шагам: поднять базу, залить документ Word, искать. Без Kubernetes.

---

## 0. Что понадобится

Базово (для обоих вариантов поиска):

- **Windows 10/11** и **Docker Desktop** (запущен, режим **Linux containers**).
- **Git** (или скачай репо ZIP с GitHub вручную).
- **Python 3.10+** (для скриптов заливки/поиска).
- Свободные порты: **13000**, **19530**, **9000**, **9001**.
- Интернет на первую загрузку образов (~1.3 ГБ).

Дополнительно — **зависит от варианта поиска**:

| Вариант поиска | Что ещё нужно | Токены |
|----------------|---------------|--------|
| **A. Без модели (BM25, по словам)** | ничего (только базовое выше) | 0 |
| **B. С моделью (по смыслу)** | **эмбеддинг-сервер** с API `/v1/embeddings` — LM Studio (локально) или любой OpenAI-совместимый | 0 (LM Studio) / платно (внешний) |

> ⚠️ **Чат-LLM ≠ эмбеддинги.** Cline/OpenAI-чат делают `/chat/completions`, а для семантики нужен
> `/v1/embeddings`. Это разные вещи. Чат-ключ годится только для AI-агента (ответ текстом), не для поиска по смыслу.

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

| Кейс | Модель | Поиск ищет | Что нужно |
|------|--------|-----------|-----------|
| **A. Без модели (BM25)** | не нужна | по словам | только Python-скрипт |
| **B. С моделью (эмбеддинги)** | нужна | по смыслу | сервер с `/v1/embeddings` (LM Studio или внешний) |

### Кейс A — БЕЗ модели (BM25, поиск по словам)

Одной командой (создаёт коллекцию и заливает текст):
```powershell
python .\scripts\docx_to_milvus_bm25.py --file "D:\FILE_WORD\moskva.docx" --collection docs_ft `
  --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123 --recreate --demo
```
Что произойдёт: текст нарежется на чанки → создастся коллекция `docs_ft` → вставится текст →
(с `--demo`) сразу покажется пример поиска.

> `--collection docs_ft` — имя коллекции (любое). `--recreate` — пересоздать заново.
> Без `--demo` просто зальёт и всё.

Проверь в Attu: обнови список — появится коллекция `docs_ft`. Открой её → увидишь строки (текст).

### Кейс B — С моделью (поиск по смыслу, эмбеддинги)

Текст превращается в вектор **моделью эмбеддингов**. Нужен сервер с API **`/v1/embeddings`**. Два подварианта.

#### B1. Локально через **LM Studio** (0 токенов, рекомендую)

1. Установи **LM Studio** (lmstudio.ai) и запусти.
2. Скачай модель: вкладка поиска моделей → найди `nomic-embed-text-v1.5` → **Download**.
3. Вкладка **Developer** (иконка сервера) → **Start Server** (порт **1234**).
4. (Опц.) Включи auth: **Server Settings → Require Authentication → Manage Tokens → Create Token**,
   скопируй токен (показывается один раз). Без auth токен не нужен.
5. Проверь, что модель видна:
   ```powershell
   curl.exe -s http://127.0.0.1:1234/v1/models -H "Authorization: Bearer <ТОКЕН>"
   ```
6. Заливай **из папки репо** (проверено: 6657 чанков ≈ 48 сек):
   ```powershell
   python .\scripts\vectorize_docx.py --file "D:\FILE_WORD\voina-i-mir.docx" --collection voina_i_mir `
     --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123 `
     --embedder api --api-base http://127.0.0.1:1234/v1 --api-key "<ТОКЕН LM STUDIO>" `
     --api-model text-embedding-nomic-embed-text-v1.5 --batch 64 --recreate
   ```

| Параметр | Значение для LM Studio |
|----------|------------------------|
| `--api-base` | `http://127.0.0.1:1234/v1` |
| `--api-key` | токен из LM Studio (или `""`, если auth выключен) |
| `--api-model` | `text-embedding-nomic-embed-text-v1.5` |

#### B2. Внешний **OpenAI-совместимый** endpoint

| Параметр | Что это | Пример |
|----------|---------|--------|
| `--api-base` | базовый URL до `/v1` | `https://api.openai.com/v1`, `http://localhost:11434/v1` (Ollama), `http://localhost:8080/v1` (TEI) |
| `--api-key` | ключ (у локальных может быть пустым) | `sk-...` |
| `--api-model` | имя модели эмбеддингов | `text-embedding-3-small`, `bge-m3` |

```powershell
python .\scripts\vectorize_docx.py --file "D:\FILE_WORD\moskva.docx" --collection docs_sem `
  --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123 `
  --embedder api --api-base https://<твой-хост>/v1 --api-key <ключ> --api-model text-embedding-3-small
```
> Трабл: `API 404` → base должен оканчиваться на `/v1`; `API 401/403` → неверный ключ;
> `не удалось подключиться` → сервер не запущен.

#### Настроить ту же модель в Attu (для поиска из UI)

Attu → **Settings → Embeddings** → **Add Provider** → заполни **Provider** (OpenAI или Custom),
**Base URL** (тот же, до `/v1`), **API Key**, **Model Name** (та же модель), **Dimension**.

> ⚠️ **Модель документов и модель запроса обязаны совпадать.**
> Для локального LM Studio из контейнера Attu адрес — `http://host.docker.internal:1234/v1`
> (проверь кнопкой Test в настройках).

> Коллекции из Кейса A (`docs_ft`) и Кейса B (`docs_sem`/`voina_i_mir`) — **разные**: это нормально.

#### B3 (опция). Своя модель в Python без сервера

```powershell
python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
python -m pip install "sentence-transformers>=3.0.0"
python .\scripts\vectorize_docx.py --file "D:\FILE_WORD\moskva.docx" --collection docs_sem `
  --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123
```
> Для поиска из Attu UI этот путь не подходит — там нужен HTTP-провайдер (B1/B2).

---

## 6. Как искать — 2 варианта

> Сначала коллекция должна быть **загружена в память** (Load), иначе Attu скажет
> «Collection must be loaded to search».

### Вариант 1 — по словам (без модели), коллекция `docs_ft`

Эта коллекция создана с функцией **BM25** (текст → sparse-вектор автоматически).

**В Attu (точно куда нажимать):**
1. Войди, выбери подключение, открой слева коллекцию **`docs_ft`**.
2. Открой вкладку **Search** (панель называется **Vector Search**).
3. Пока пусто → кнопка **Add a search request** (или **+**). Выбери тип **Full-Text**.
4. **Text Field** — выбери поле `text`.
5. **Search Text** — введите запрос словами, напр. `автоматизация развёртывания`.
6. Нажми **Search** → снизу результаты: совпавшие куски + score.

**Из Python (проверено):**
```powershell
python .\scripts\docx_to_milvus_bm25.py --file "D:\FILE_WORD\moskva.docx" --collection docs_ft `
  --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123 --demo `
  --query "автоматизация развёртывания контейнеров"
```
> BM25 ищет **совпадения слов**. Синонимы не находит → нужен Вариант 2.

### Вариант 2 — по смыслу (с моделью), коллекция `docs_sem`/`voina_i_mir`

Вектор запроса считает модель. Есть 3 способа:

#### Способ A — из Attu UI (нужен embedding-провайдер в настройках)

1. Сначала настрой провайдер эмбеддингов: **Settings → Embeddings → Add Provider**
   (**Base URL** до `/v1`, **API Key**, **Model Name** — та же модель, что при заливке).
   Для LM Studio из контейнера Attu: `http://host.docker.internal:1234/v1`.
2. Открой коллекцию (`voina_i_mir`) → вкладка **Search**.
3. **Add a search request** → тип **Vector**.
4. **Vector Field** — выбери поле `vector`.
5. Вместо ручного вектора выбери **Similarity Text** и введи фразу
   (подсказка: *Enter text to find approximately similar content*) — Attu сам посчитает вектор запроса.
6. **Metric** — `COSINE`. Нажми **Search**.

> Если п.1 не настроен, Attu напишет «No embedding providers configured» и Similarity Text не сработает.

#### Способ B — из Python через тот же endpoint (проверено)

```python
import requests
from pymilvus import MilvusClient

BASE   = "http://127.0.0.1:1234/v1"      # тот же base, что при заливке
KEY    = "<ТОКЕН LM STUDIO>"             # или "" если auth выключен
MODEL  = "text-embedding-nomic-embed-text-v1.5"   # та же модель
QUERY  = "описание Бородинского сражения"

r = requests.post(f"{BASE}/embeddings",
                  headers={"Authorization": f"Bearer {KEY}"},
                  json={"model": MODEL, "input": QUERY}, timeout=60)
qvec = r.json()["data"][0]["embedding"]

c = MilvusClient(uri="http://127.0.0.1:19530", token="root:MilvusDemo123")
for h in c.search("voina_i_mir", data=[qvec], anns_field="vector", limit=3, output_fields=["content"])[0]:
    print(h["distance"], h["entity"]["content"][:120].replace("\n", " "))
```

#### Способ C — локальной моделью bge-m3 (если заливал B3)

```python
from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("BAAI/bge-m3")
qvec = m.encode(["как масштабировать приложение"], normalize_embeddings=True)[0].tolist()
c = MilvusClient(uri="http://127.0.0.1:19530", token="root:MilvusDemo123")
for h in c.search("docs_sem", data=[qvec], anns_field="vector", limit=3, output_fields=["content"])[0]:
    print(h["distance"], h["entity"]["content"][:100])
```

> Вариант 2 ищет **по смыслу**: «канонада» найдётся по запросу «Бородинское сражение», хотя этих слов рядом нет.

---

## 7. Пример end-to-end: `moskva.docx` (заливка + 2 вопроса)

Файл `D:\FILE_WORD\moskva.docx` (МГТУ им. Баумана, «Приоритет 2030», космические проекты)
даёт **12 чанков**. Заливаем **оба** варианта (команды — из папки репо):

```powershell
# Вариант 1 — без модели (BM25):
python .\scripts\docx_to_milvus_bm25.py --file "D:\FILE_WORD\moskva.docx" --collection moskva_ft `
  --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123 --recreate

# Вариант 2 — с моделью (LM Studio):
python .\scripts\vectorize_docx.py --file "D:\FILE_WORD\moskva.docx" --collection moskva_sem `
  --host 127.0.0.1 --port 19530 --user root --password MilvusDemo123 `
  --embedder api --api-base http://127.0.0.1:1234/v1 --api-key "<ТОКЕН LM STUDIO>" `
  --api-model text-embedding-nomic-embed-text-v1.5 --batch 64 --recreate
```

Получится 2 коллекции: **`moskva_ft`** (поиск по словам) и **`moskva_sem`** (поиск по смыслу).

### Вопрос 1 — прямой поиск (BM25), коллекция `moskva_ft`

Вопрос (ключевые слова из текста): **«Приоритет 2030»**.

- **В Attu:** открой `moskva_ft` → вкладка **Search** → **Add a search request** → **Full-Text** →
  **Text Field** = `text` → **Search Text** = `Приоритет 2030` → **Search**.
- **Результат** (проверено): верхний чанк — заголовок «БАУМАНА И ПРОГРАММА «ПРИОРИТЕТ 2030»» (score ≈ 2.7).

> Итог: BM25 находит **по словам**. Работает без модели.

### Вопрос 2 — семантический поиск (эмбеддинги), коллекция `moskva_sem`

Вопрос **без точных слов** из текста: **«куда университет отправляет спутники и ракеты-носители»**.

- **В Attu:** открой `moskva_sem` → **Search** → **Add a search request** → **Vector** →
  **Vector Field** = `vector` → **Similarity Text** = вопрос → **Metric** = `COSINE` → **Search**.
  (Перед этим — настройка **Settings → Embeddings**, см. раздел 5.)
- **Результат** (проверено): поднимаются чанки про «Космический корабль для Марса»,
  «Космический кабель», ракеты-носители — хотя слов «спутники»/«ракеты» в тексте может не быть.

> Итог: семантика находит **по смыслу**. Нужна модель.

### Вопрос 3 — ответ текстом через LLM (AI-агент)

Настрой LLM (**Settings → LLM Configuration**, см. раздел 9), затем в коллекции `moskva_sem`
открой панель **AI / Agent** и задай: **«Какие космические проекты есть у МГТУ им. Баумана?»** —
агент возьмёт top-k чанков и **сформулирует ответ** через LLM.

---

## 8. Обратная выгрузка: Milvus → файл («развекторизация»)

Milvus хранит **исходный текст** чанков (поле `text` или `content`), поэтому данные можно вернуть
в файл. «Отменить» эмбеддинги в вектор нельзя, но текст — да.

### A. Скрипт (txt / docx / jsonl)

```powershell
# в обычный текст:
python .\scripts\milvus_export.py --collection moskva_sem --out moskva_back.txt `
  --user root --password MilvusDemo123

# обратно в Word:
python .\scripts\milvus_export.py --collection moskva_sem --out moskva_back.docx --format docx `
  --user root --password MilvusDemo123

# в JSONL (каждая строка = чанк):
python .\scripts\milvus_export.py --collection moskva_ft --out moskva_back.jsonl --format jsonl `
  --user root --password MilvusDemo123
```
Скрипт сам определяет текстовое поле (`text`/`content`) и сортирует чанки по `chunk_index`.
Проверено: `moskva_sem` → 12 строк → txt/docx/jsonl OK.

### B. Через Attu UI

1. Открой коллекцию → **Load** (обязательно).
2. Меню коллекции → **Export Data** (окно «Export "<collection>"»).
3. **Save to** — выбери место (Browse / системный диалог), **Format** — `JSONL` или `Parquet`.
4. (опц.) **Filter expression** — напр. `chunk_index < 5`.
5. **Start Export** → файл появится по указанному пути.
## 9. AI-агент: вопрос по документу текстом (LLM)

Поиск (раздел 6) отдаёт **куски** текста. Если хочешь, чтобы **модель написала ответ** по этим
кускам — подключи LLM: **Settings → LLM Configuration**.

| Поле | Что писать (пример — Cline-шлюз) |
|------|----------------------------------|
| **Provider** | `OpenAI` |
| **Endpoint URL** | `https://api.cline.bot/api` |
| **Model Name** | `openai/gpt-6.1-sol` |
| **API Key** | `sk_...` |
| **Temperature** | `0` (или 0.7) |
| **Max Tokens** | `4096` |

- **Endpoint URL** — это **Base URL** (без пути!). Attu к провайдеру `OpenAI` сам добавит
  `/v1/chat/completions`. Т.е. получится ровно `https://api.cline.bot/api/v1/chat/completions`.
- **Model Name** — полный id с провайдером (напр. `openai/gpt-6.1-sol`, `anthropic/claude-sonnet-5.5`).
- Проверка: кнопка **Test** в этой форме.

> ⚠️ LLM (чат) — это **не** эмбеддинги. Cline-ключ подходит **только** для чата/агента.
> Для семантического поиска (раздел 6, Вариант 2) нужен embedding-провайдер (LM Studio/OpenAI-embeddings).

После сохранения: открой коллекцию → панель **AI / Agent** → задай вопрос
(«как Толстой описывает Бородино?») — агент берёт top-k чанков и отвечает через LLM.

## 10. Остановить / удалить

```powershell
docker compose stop        # пауза (данные сохраняются)
docker compose down        # удалить контейнеры (данные в volumes остаются)
docker compose down -v     # удалить ВСЁ вместе с данными (чистый старт)
```

---

## 11. Если что-то не так

| Симптом | Что делать |
|---------|-----------|
| `Connection Unavailable ... UNAUTHENTICATED` в Attu | В Connect проверь: host `milvus`, user `root`, password `MilvusDemo123`. Удали старое соединение без пароля и подключись снова. |
| Порт занят (`13000`/`19530`) | В `docker-compose.yml` поменяй левую часть в `ports` (напр. `"14000:3000"`), затем `docker compose up -d`. |
| `milvus-standalone` не healthy | Дай Docker больше памяти (Settings → Resources, ≥ 6 ГБ) и подожди 2–3 мин. Смотри `docker compose logs -f milvus`. |
| `ERROR: нужен python-docx` | `python -m pip install -r .\scripts\requirements-vectorize.txt` |
| `ERROR: --embedder offline требует sentence-transformers` | Используй `--embedder api` (Кейс B, OpenAI-compatible) или поставь локальную модель. |
| `ERROR: API 401/403` при `--embedder api` | Проверь `--api-base` (должен оканчиваться на `/v1`), ключ и имя модели. |
| `ERROR: API 404` | Неверный путь: base должен быть `https://host/v1` (скрипт добавит `/embeddings`). |
| В Attu «No embedding providers configured» | Настрой **Settings → Embeddings → Add Provider** (для семантического поиска из UI). |
| В Attu «Collection must be loaded to search» | Нажми **Load** у коллекции. |
| Attu не видит LM Studio на 127.0.0.1 | Из контейнера хост — `http://host.docker.internal:1234/v1` (Base URL в настройках). |
| LLM не отвечает / 401 | Проверь Endpoint URL (только base, без пути), ключ и Model Name. Cline: `https://api.cline.bot/api`. |
| Torch падает на GPU (RTX 50xx) | Нужен CUDA-12.8: `pip install torch --index-url https://download.pytorch.org/whl/cu128` |
| Не понимаю, нужна ли модель | Поиск по словам → **не нужна** (Вариант 1). Поиск по смыслу → **нужна** (Вариант 2). |

---

## 12. Шпаргалка (весь путь)

```powershell
git clone https://github.com/one6way/milvus-attu-doc.git; cd milvus-attu-doc
docker compose up -d                      # поднять;  ждать healthy milvus-standalone
# браузер: http://127.0.0.1:13000  (вход admin / AttuDemo123!  -> Connect milvus/19530 root/MilvusDemo123)
python -m pip install -r .\scripts\requirements-vectorize.txt

# Кейс A — БЕЗ модели (поиск по словам):
python .\scripts\docx_to_milvus_bm25.py --file "D:\FILE_WORD\moskva.docx" --collection docs_ft --user root --password MilvusDemo123 --recreate --demo

# Кейс B1 — С моделью локально (LM Studio, 0 токенов):
python .\scripts\vectorize_docx.py --file "D:\FILE_WORD\moskva.docx" --collection docs_sem --user root --password MilvusDemo123 --embedder api --api-base http://127.0.0.1:1234/v1 --api-key "<ТОКЕН LM STUDIO>" --api-model text-embedding-nomic-embed-text-v1.5 --batch 64 --recreate

# Кейс B2 — С моделью через внешний OpenAI-compatible:
python .\scripts\vectorize_docx.py --file "D:\FILE_WORD\moskva.docx" --collection docs_sem --user root --password MilvusDemo123 --embedder api --api-base https://<host>/v1 --api-key <key> --api-model text-embedding-3-small

# Обратная выгрузка (Milvus -> файл):
python .\scripts\milvus_export.py --collection docs_sem --out moskva_back.docx --format docx --user root --password MilvusDemo123
```
> Оба скрипта берут Milvus из `--host 127.0.0.1 --port 19530` по умолчанию (можно не указывать).

Что где настраивается в Attu:
- **Settings → Embeddings** — модель для семантического поиска (Вариант 2, из UI).
- **Settings → LLM Configuration** — чат-модель для AI-агента (раздел 9).
- **Export Data** (меню коллекции) — выгрузка данных (раздел 8).