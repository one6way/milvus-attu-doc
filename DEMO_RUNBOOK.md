# DEMO RUNBOOK — Milvus + Attu по шагам (с реальными логами)

Прогон на стенде Windows + Docker Desktop. Каждый блок — команда и её **фактический вывод**
(логи усечены, но не выдуманы). Всё, кроме клонирования, воспроизведено заново.

Дата прогона: 2026-10-01. Версии: `milvusdb/milvus:v3.0.1`, `zilliz/attu:v3.0.1`,
эмбеддинги `text-embedding-nomic-embed-text-v1.5` (LM Studio, dim 768).

---

## Шаг 2. Поднять Milvus + Attu

```powershell
cd milvus-attu-doc
docker compose up -d
docker compose ps
```

Лог:
```
 Container milvus-etcd Started
 Container milvus-minio Started
 Container milvus-standalone Started
 Container attu Started

NAME                STATUS
attu                Up 57 minutes
milvus-etcd         Up 57 minutes (healthy)
milvus-minio        Up 57 minutes (healthy)
milvus-standalone   Up 57 minutes (healthy)
```
**Ждём `milvus-standalone` = healthy (~1–2 мин).** Это признак готовности базы.
Порты: Attu `13000`, Milvus `19530`, MinIO console `9001`.

---

## Шаг 3. Вход в Attu

**Действия:** браузер → **http://127.0.0.1:13000** → логин `admin` / `AttuDemo123!` →
экран **Connection**: host `milvus`, port `19530`, user `root`, password `MilvusDemo123` → **Connect**.

Лог (страница входа отдаётся):
```
HTTP 200
title: Sign in - Attu
```
Лог (проверка подключения к Milvus теми же кредами):
```
connected OK, dbs= ['default']
```
> Если справа вверху «Connection Unavailable» — неверный host/пароль.
> Host именно `milvus` (не `127.0.0.1`) — Attu ходит в базу изнутри контейнера.

---

## Шаг 4. Интерфейс Attu

**Действия:** слева **Databases → default → Collections**. Открыть коллекцию → вкладки
**Data** (строки), **Query** (фильтр + поля), **Search**. Меню ⋮ → **Load / Export Data / Drop**.
Шестерёнка → **Settings** (Embeddings, LLM).

Лог (список коллекций на момент прогона; `demo_*` — разовые для демонстрации):
```
NAME             ROWS   TYPE
demo_ft          6657   BM25(sparse)
demo_sem         6657   SEMANTIC(vector)
docs_ft            20   BM25(sparse)
docs_sem           20   SEMANTIC(vector)
docx_fulltext      20   BM25(sparse)
moskva_ft          12   BM25(sparse)
moskva_sem         12   SEMANTIC(vector)
voina_i_mir      6657   SEMANTIC(vector)
voina_i_mir_ft   6657   BM25(sparse)
```
> Метка **Not Loaded** → кнопка **Load** (иначе поиск/чтение не работают). Все коллекции — Loaded.

---

## Шаг 5. Залить Word-документ

Файл: `samples/voina-i-mir.docx`.

### 5A. БЕЗ модели (BM25, поиск по словам)
```powershell
python .\scripts\docx_to_milvus_bm25.py --file ".\samples\voina-i-mir.docx" `
  --collection demo_ft --user root --password MilvusDemo123 --recreate
```
Лог:
```
[1/3] текст из .\samples\voina-i-mir.docx
      блоков=23419 чанков=6657
[2/3] create demo_ft (BM25, без модели)
[3/3] вставлено 6657 строк в demo_ft (uri=http://127.0.0.1:19530)
   время: 6,9 c
```
Модель не нужна. Есть поле `text` + `sparse` (BM25-функция).

### 5B. С моделью эмбеддингов (поиск по смыслу)
```powershell
python .\scripts\vectorize_docx.py --file ".\samples\voina-i-mir.docx" --collection demo_sem `
  --user root --password MilvusDemo123 --embedder api `
  --api-base http://192.168.1.107:1234/v1 --api-key "<ТОКЕН LM STUDIO>" `
  --api-model text-embedding-nomic-embed-text-v1.5 --batch 64 --recreate
```
Лог:
```
[1/4] извлечение текста: .\samples\voina-i-mir.docx
      блоков=23419 чанков=6657 символов=4284573
[2/4] эмбеддинги (api)
[api] endpoint=http://192.168.1.107:1234/v1/embeddings model=text-embedding-nomic-embed-text-v1.5
      векторов=6657 dim=768 за 48.6s
[3/4] запись в Milvus
[milvus] create collection=demo_sem dim=768 metric=COSINE index=AUTOINDEX
[4/4] готово: коллекция=demo_sem вставлено=6657 uri=http://127.0.0.1:19530
   время: 54,5 c
```
Есть поле `vector` (768) + `content`. Модель — **только** `nomic-embed-text-v1.5`.

---

## Шаг 6. Поиск — 2 способа

### 6A. По словам (BM25, без модели) — коллекция `demo_ft`
**Действия:** открыть `demo_ft` → **Search** → **Add a search request** → **Full-Text** →
**Text Field** `text` → **Search Text** `Бородинское сражение` → **Search**.

Лог:
```
'Бородинское сражение' (13 ms)
    score=15.49 chunk=3473: Действия Понятовского против Утицы и Уварова на правом фланге французо
    score=14.10 chunk=3455: XIX.  24-го было сражение при Шевардинском редуте, 25-го не было пущен
'Наташа Ростова' (2 ms)
    score=9.38 chunk=6521: ова.  Глава VIII | Молодежь дома Ростовых: Наташа, Николай, Петя, Соня
    score=7.77 chunk=6561: I | Бал «подростков» у Иогеля. Особенное оживление Наташи и Сони на эт
```

### 6B. По смыслу (эмбеддинги) — коллекция `demo_sem`
**Действия:** сначала **Settings → Embeddings → Add Provider** (Provider `OpenAI`,
Base URL `http://host.docker.internal:1234/v1`, Model `text-embedding-nomic-embed-text-v1.5`,
Dimension `768`) → **Test → Save**. Затем: открыть `demo_sem` → **Search** →
**Add a search request** → **Vector** → **Vector Field** `vector` → **◉ Similarity Text** →
ввести фразу → **Metric** `COSINE` → **Search**.

Лог:
```
'казаки атакуют французов' (5 ms) dim=768
    dist=0.823 chunk=450:  армия должна была с разных сторон сделать нападение на французов. Ста
    dist=0.820 chunk=4675: бря началось движение выступавших французов: ломались кухни, балаганы,
'мысли Андрея о небе' (3 ms) dim=768
    dist=0.815 chunk=2503: не связать себя, теперь ездил к ней смело каждый день и обращался с не
    dist=0.811 chunk=3626: идал убитых и раненых, хотя многие падали недалеко от него. С улыбкой,
```
> Без настройки Embeddings графа **Similarity Text** будет серая («No embedding providers configured»).

### 6C. «Пройтись» по документу без поиска — вкладка Query
**Действия:** `demo_sem` → **Query** → **Filter** `chunk_index < 3` → поля `chunk_index, content` → **Query**.

Лог:
```
chunk 0: Лев Николаевич Толстой  Война и мир  Государственное издательство «Худ
chunk 1: Настоящее издание представляет собой электронную версию 90-томного соб
chunk 2: го Государственный музей Л.Н. Толстого, музей-усадьба «Ясная Поляна» в
```
Менять фильтр (`chunk_index >= 10 and chunk_index < 20`) — листать дальше.

---

## Шаг 7. Выгрузка документа назад

```powershell
python .\scripts\milvus_export.py --collection demo_sem --out demo_out.txt --format txt --user root --password MilvusDemo123
python .\scripts\milvus_export.py --collection demo_sem --out demo_out.docx --format docx --user root --password MilvusDemo123
```
Лог:
```
[milvus] demo_sem: строк=6657 текстовое поле=content формат=txt
OK: demo_out.txt   (7611228 bytes)
[milvus] demo_sem: строк=6657 текстовое поле=content формат=docx
OK: demo_out.docx  (1883280 bytes)

выгруженный .docx -> абзацев: 59143
   начало:
      Лев Николаевич
      Толстой
      Война и мир
```
Через UI: `demo_sem` → ⋮ **Export Data** → Format `JSONL`/`Parquet` → **Start Export**.
> Вёрстка/картинки/таблицы не вернутся — только плоский текст по порядку `chunk_index`.

---

## Настройка Attu (сделать ДО показа 6B)

**Settings → Embeddings → Add Provider**

| Поле | Значение |
|------|----------|
| Provider | `OpenAI` |
| Base URL | `http://host.docker.internal:1234/v1` |
| API Key | токен LM Studio (`sk-lm-...`) |
| Model Name | `text-embedding-nomic-embed-text-v1.5` |
| Dimension | `768` |

**Settings → LLM Configuration** (для AI-агента, если показываешь):

| Поле | Значение |
|------|----------|
| Provider | `OpenAI` |
| Endpoint URL | `http://host.docker.internal:1234` (base, без `/v1/...`) |
| Model Name | `qwen3.6-35b-a3b` |
| API Key | токен LM Studio |

---

## Очистка

```powershell
docker compose stop        # пауза (данные сохраняются)
docker compose down        # убрать контейнеры (данные в volumes остаются)
docker compose down -v     # удалить всё вместе с данными
```
`demo_ft`/`demo_sem` в этом прогоне создавались только для демонстрации и удалены — в стенде
остаются `voina_i_mir` (семантика), `voina_i_mir_ft` (BM25) и `moskva_*`/`docs_*`.