# Milvus + Attu (Kubernetes)

Минимальный репозиторий для развёртывания **Milvus 3.0** и **Attu 3.0** в Kubernetes
(`docker-desktop`, kind, любой кластер) и для загрузки в Milvus текста из документов Word.

Состав — **только необходимое**: нет образов, дампов, бэкапов и сторонних проектов.

## Что внутри

| Путь | Назначение |
|------|------------|
| `chart/attu/` | Helm-чарт Attu 3.0 (bootstrap-админ, PVC для `/data`, порт 3000) |
| `values/milvus.yaml` | Values Milvus 3.0: standalone, messageQueue=woodpecker, StorageClass `standard`, ClusterIP |
| `values/attu.yaml` | Values Attu: образ `zilliz/attu:v3.0.1`, адрес Milvus `milvus:19530` |
| `scripts/install-milvus-attu.ps1` | **Один скрипт**: ставит Milvus (официальный чарт) + Attu |
| `scripts/share-attu.ps1` | Порт-форвард + публичный туннель: даёт ссылку на Attu для **других ПК** |
| `scripts/share-milvus.ps1` | Порт-форвард + TCP-туннель: доступ к Milvus для **pymilvus/SDK** с других ПК |
| `scripts/vectorize_docx.py` | Векторизация `.docx` → коллекция Milvus (offline-модель или OpenAI-совместимый API) |
| `scripts/requirements-vectorize.txt` | Зависимости Python для векторизации |
| `.gitlab-ci.yml` | Пайплайн: lint + рендер чартов (best practice) |

Milvus ставится из **официального** чарта (`zilliztech/milvus-helm`, версия **5.0.30** → образ
`milvusdb/milvus:v3.0.1`), а не из вендоренного 673-файлового чарта. Attu — из нашего чарта `chart/attu`.

## Требования

- Kubernetes ≥ 1.20 и `kubectl`
- Helm ≥ 3.14
- Docker (containerd/Docker Desktop)
- StorageClass `standard` (в Docker Desktop есть по умолчанию) — либо поправьте `values/milvus.yaml`
- Интернет для pull официальных образов (`milvusdb/*`, `zilliz/attu`)

## Установка (одна команда)

```powershell
# Показать план без установки (helm template):
.\scripts\install-milvus-attu.ps1 -DryRun

# Установить:
.\scripts\install-milvus-attu.ps1
```

Скрипт делает:
1. `helm repo add milvus https://zilliztech.github.io/milvus-helm/`
2. `helm upgrade --install milvus milvus/milvus --version 5.0.30 -n milvus --create-namespace -f values/milvus.yaml --wait`
3. `helm upgrade --install attu ./chart/attu -n milvus -f values/attu.yaml --set image.repository=zilliz/attu --set image.tag=v3.0.1 --wait`
4. Печатает команды доступа.

### Доступ

```powershell
# Attu (веб-UI)
kubectl -n milvus port-forward svc/attu 13000:3000   # → http://127.0.0.1:13000

# Milvus (gRPC) для скриптов/pymilvus
kubectl -n milvus port-forward svc/milvus 19530:19530
```

При первом входе Attu попросит создать админа (свой логин Attu). В форме подключения к Milvus
укажите адрес **`milvus:19530`** (адрес резолвится внутри pod'а, не `127.0.0.1`).

## Загрузка документов Word

```powershell
python -m pip install -r .\scripts\requirements-vectorize.txt

# 1. Milvus доступен
kubectl -n milvus port-forward svc/milvus 19530:19530

# 2. Векторизовать документ (локальная модель, GPU→CPU fallback, 0 токенов)
python .\scripts\vectorize_docx.py --file "C:\docs\doc.docx" --collection my_docs

# Альтернатива: внешний OpenAI-совместимый векторизатор (TEI/Ollama/OpenAI)
python .\scripts\vectorize_docx.py --file .\doc.docx --collection my_docs `
  --embedder api --api-base http://localhost:8080/v1 --api-model bge-m3

# Проверить чанки без модели и Milvus:
python .\scripts\vectorize_docx.py --file .\doc.docx --dry-run --echo-chunks 3
```

Схема коллекции: `id` (auto), `vector` (FLOAT_VECTOR), `content`, `source`, `chunk_index`.

## Снятие стенда

```powershell
helm uninstall attu milvus -n milvus
kubectl delete ns milvus
```

## CI/CD (GitLab)

`.gitlab-ci.yml` — стадии и джобы:

| Стадия | Джоб | Что делает | Раннер |
|--------|------|-----------|--------|
| lint | `lint:yamllint` | Проверка YAML (`.gitlab-ci.yml`, `values/`) | shared |
| lint | `lint:powershell` | Синтаксис PowerShell | shared |
| lint | `lint:python` | Компиляция Python | shared |
| lint | `lint:helm` | `helm lint` обоих чартов | shared |
| package | `package:charts` | Сборка Helm-чартов в `dist/*.tgz` (artifacts) | shared |
| check | `check:artifacts` | Проверка артефактов сборки | shared |
| validate | `prep:env` | Проверка окружения и наличия файлов | shared |
| validate | `validate:render` | `helm template` обоих чартов | shared |
| deploy | `deploy:milvus` | Установка Milvus | shared + **agent** |
| deploy | `deploy:attu` | Установка Attu | shared + **agent** |
| verify | `verify:stack` | Проверка установленного ПО | shared + **agent** |

Автоматические джобы (lint/package/check/validate) работают на shared-раннере GitLab.com
и не требуют доступа к кластеру. Джобы `deploy:*` и `verify:stack` тоже идут на **shared**,
но попадают в кластер через **GitLab Agent for Kubernetes**, поэтому идут на **одном и том же**
кластере по цепочке «Milvus → Attu → проверка».

### Требование: активный раннер

На GitLab.com у нового бесплатного аккаунта shared-раннеры неактивны (статус `paused`).
Лечится так:

1. GitLab → (аватар) → **Edit profile → Account** → верификация личности.
2. Проект → **Settings → CI/CD → Runners** → включить shared runners.

### GitLab Agent для deploy/verify (self-hosted runner не нужен)

Джобы `deploy:*` и `verify:stack` выполняются на **shared-раннерах GitLab.com** через
**GitLab Agent for Kubernetes** (Free). Агент ставится в кластер один раз, сам соединяется
с `kas.gitlab.com` — входящий доступ к кластеру не требуется.

Что сделано в проекте:
1. Конфиг агента: `.gitlab/agents/milvus-k8s/config.yaml` (разрешает CI проекта управлять кластером).
2. Агент установлен в кластер (namespace `gitlab-agent`):
   ```powershell
   helm repo add gitlab https://charts.gitlab.io
   helm repo update
   helm upgrade --install milvus-k8s gitlab/gitlab-agent -n gitlab-agent --create-namespace `
     --set config.token=<AGENT_TOKEN> --set config.kasAddress=wss://kas.gitlab.com
   ```
3. Джобы используют контекст агента (`environment.kubernetes.agent` + `KUBE_CONTEXT`).

Запуск установки (любой способ):
- **Тег** с префиксом `deploy-` (best practice для релизов):
  ```powershell
  git tag deploy-v1
  git push origin deploy-v1
  ```
- или в UI: **Run pipeline** → переменная **`DEPLOY=true`**.

Обычный push деплой не трогает (`rules` срабатывают только на тег `deploy-*`
или переменную `DEPLOY=true`), поэтому пайплайн остаётся зелёным.

Обновить/переустановить агента:
```powershell
helm upgrade milvus-k8s gitlab/gitlab-agent -n gitlab-agent --set config.token=<AGENT_TOKEN> --set config.kasAddress=wss://kas.gitlab.com
kubectl -n gitlab-agent get pods
```

### Проверка без раннера (локально)

Тот же набор статических проверок:

```powershell
.\scripts\validate-all.ps1
```

---

## Демо: показать «пайплайн → Milvus+Attu → векторный поиск»

### Короткий путь: «нажал кнопку в GitLab → получил адрес Attu»

**Нужен ли второму человеку Kubernetes, kubectl, helm? — НЕТ.**

Attu — это веб-сервер *внутри* кластера; браузер общается только с Attu, а до Milvus
достукивается сам Attu (server-side). Поэтому человеку на другом ПК достаточно
**браузера** и ссылки. Кластер, kubectl, helm, git — не нужны вообще.

Так работает потому, что ваш кластер живёт за NAT, а наружу смотрит только туннель:

```
браузер (другой ПК) ──https──> cloudflared/trycloudflare ──> ваш ПК ──> kubectl port-forward ──> pod attu ──> milvus:19530
```

> Скрипты `share-attu.ps1` / `share-milvus.ps1` запускаются **только на ПК владельца
> кластера** — им нужен `kubectl` и доступ к кластеру. Другой человек их не запускает:
> он просто открывает ссылку (Attu) или подключается по выданному адресу (pymilvus).

**Шаг 1. Владелец кластера — один раз поднимает туннель** (оставить окно открытым):

```powershell
.\scripts\share-attu.ps1 -InstallCloudflared
# ==> публично (для других ПК): https://<случайные-слова>.trycloudflare.com
```

Аккаунт Cloudflare и домен не нужны. Затем записать адрес в GitLab, чтобы он был
виден всем: **Settings → CI/CD → Variables → `ATTU_PUBLIC_URL`** = эта ссылка
(если не задать — в GitLab будет `http://127.0.0.1:3000`, т.е. только локально).

**Шаг 2. Второй человек — нажимает «кнопку» и открывает Attu** (только браузер):

1. GitLab → проект → **Code → Tags → New tag** → имя `deploy-v1` → *Create tag*.
   Это и есть кнопка: тег `deploy-*` запускает пайплайн
   (`deploy:milvus` → `deploy:attu` → `verify:stack`) на вашем кластере через агента.
2. **Operate → Environments → milvus → Open** — GitLab откроет `ATTU_PUBLIC_URL`.
   Тот же адрес печатается в конце лога джобы `verify:stack`
   (`Attu для браузера (в т.ч. с другого ПК): ...`).
3. Логин `admin` / `AttuDemo123!` → **Connect**: host `milvus`, port `19530` → тестируем.

> Туннель живёт, пока открыто окно `share-attu.ps1`. Пароль для публичной ссылки
> лучше сменить: `Settings → CI/CD → Variables` → `ATTU_ADMIN_PASSWORD` (Masked),
> затем перезапустить пайплайн тегом.

### Когда Kubernetes всё же понадобится

Только если человек хочет **свой** стенд, а не пользоваться вашим:

| Хочу | Что нужно |
|------|-----------|
| Тестировать ваш Milvus через ваш Attu | **только браузер** + ссылка |
| Работать с вашим Milvus через pymilvus | `pip install pymilvus` + адрес из `share-milvus.ps1` (кластер не нужен) |
| Развернуть свой стенд | Docker Desktop k8s (≥4 CPU/8 GB) + helm + kubectl + **свой** GitLab Agent + **свой** `ATTU_PUBLIC_URL` |

### Развернуть у СЕБЯ (свой стенд)

> **Важно:** агент `milvus-k8s` установлен **в этот локальный кластер** — через него pipeline
> деплоит именно сюда. Чтобы развернуть у себя, нужен **свой** агент в **своём** кластере
> (токен агента переиспользовать нельзя).

1. **Docker Desktop** → Settings → Kubernetes → *Enable Kubernetes*; Resources: **≥ 4 CPU, ≥ 8 GB RAM**
   (Milvus standalone + etcd + MinIO + Attu на одном узле).
2. `kubectl`, `helm ≥ 3.14`, `git`.
3. **Свой** агент: создать в проекте (`Operate → Kubernetes clusters`) и поставить в свой кластер:
   ```powershell
   helm repo add gitlab https://charts.gitlab.io; helm repo update
   helm upgrade --install milvus-k8s gitlab/gitlab-agent -n gitlab-agent --create-namespace `
     --set config.token=<СВОЙ_AGENT_TOKEN> --set config.kasAddress=wss://kas.gitlab.com
   ```
4. Указать **свой** путь агента: `.gitlab-ci.yml` → `.deploy_base.variables.KUBE_CONTEXT`
   и `environment.kubernetes.agent` (сейчас `nikobellic438/milvus:milvus-k8s`).
5. Запушить тег: `git tag deploy-v1; git push origin deploy-v1`.
6. Дать доступ другим: `.\scripts\share-attu.ps1 -InstallCloudflared` → адрес в `ATTU_PUBLIC_URL`.

### Шаги демо (кластер владельца)

```powershell
# 1) Деплой всего стенда одной командой CI:
git tag deploy-v3 ; git push origin deploy-v3      # deploy:milvus -> deploy:attu -> verify:stack

# 2) Доступ к Attu (сервис ClusterIP):
kubectl -n milvus port-forward svc/attu 3000:3000
#    браузер: http://127.0.0.1:3000
```

**Логин Attu 3.0** (у приложения своя авторизация; задаётся в `values/attu.yaml` → `admin`):

| Поле | Значение |
|------|----------|
| Username | `admin` |
| Password | `AttuDemo123!` |

> Пароль-политика Attu: 8–128 символов и минимум **3 класса** из 4 (A-Z, a-z, 0-9, спецсимволы).
> В продакшене пароль задавайте через CI/CD variable `ATTU_ADMIN_PASSWORD` / Secret, не в git.

### Что показать в Attu

1. **Connect** → host `milvus` (не `localhost`!), port `19530`,
   **User** `root`, **Password** `MilvusDemo123` (см. ниже про авторизацию) → *Connect*.
2. **Databases** → создать БД `demo` (кнопка *Create Database*).
3. **Create Collection** → например `docs`:
   - поле `id` (Int64, primary), `text` (**TEXT**/**VarChar**), `vector` (**FloatVector**, dim = размерность модели),
   - индекс по `vector` (тип `AUTOINDEX` или `HNSW`, метрика `COSINE`/`L2`).
4. **Загрузить вектор** — один из вариантов:
   - *Data → Insert*: вставить JSON-строку с полем `vector: [...]` (готовые эмбеддинги);
   - *Data → Import*: загрузить JSON/JSONL-файл (Attu импортирует чанками);
   - из репозитория: `scripts/vectorize_docx.py` (Word → эмбеддинги → коллекция Milvus).
5. **Search / Query** → задать вектор или текст → увидеть `hit`.
6. **LLM API (AI Workbench)** → настройки модели в UI: OpenAI-совместимый **base URL** + **API key**
   (например `https://api.openai.com/v1`), затем чат-агент по данным коллекции.

### Авторизация Milvus (обязательна перед публикацией порта)

В `values/milvus.yaml` включена авторизация — иначе любой, кто дошёл до 19530, может
читать/писать/удалять коллекции:

```yaml
extraConfigFiles:
  user.yaml: |+
    common:
      security:
        authorizationEnabled: true
        defaultRootPassword: MilvusDemo123
```

| Кто | Логин | Пароль |
|-----|-------|--------|
| Milvus (root) | `root` | `MilvusDemo123` |
| Attu (само приложение) | `admin` | `AttuDemo123!` |

> `defaultRootPassword` применяется **только при первой инициализации**. На уже
> работающем Milvus пароль root так не сменить — используйте
> `MilvusClient.update_password(...)` (см. пример ниже).

### Работа с Milvus напрямую (pymilvus / SDK) с другого ПК

Attu в браузере — это UI. Если человеку нужен **pymilvus**, он ходит на gRPC-порт
Milvus (19530) напрямую, поэтому нужен **отдельный** туннель именно к Milvus
(туннель Attu публикует только 3000):

```powershell
# на ПК владельца кластера:
.\scripts\share-milvus.ps1 -Tunnel ngrok -InstallNgrok
# выведет host/port и готовый сниппет:
#   c = MilvusClient(uri="http://<host>:<port>", token="root:MilvusDemo123")
```

На ПК клиента (нужен только `pip install pymilvus`):

```python
from pymilvus import MilvusClient
c = MilvusClient(uri="http://<host>:<port>", token="root:MilvusDemo123")
c.create_collection("demo", dimension=4)
c.insert("demo", [{"id": 1, "vector": [0.1, 0.2, 0.3, 0.4]}])
c.flush("demo")
print(c.search("demo", [[0.1, 0.2, 0.3, 0.4]], limit=1))
```

Векторизация Word-документа в ту же коллекцию (`--user`/`--password`):

```powershell
kubectl -n milvus port-forward svc/milvus 19530:19530   # или адрес туннеля
python scripts/vectorize_docx.py doc.docx --host <host> --port <port> --user root --password MilvusDemo123
```

Смена пароля root (работает и на уже развёрнутом Milvus):

```python
from pymilvus import MilvusClient
c = MilvusClient(uri="http://127.0.0.1:19530", token="root:Milvus")
c.update_password(user_name="root", old_password="Milvus", new_password="MilvusDemo123")
```

Проверено на этом стенде: без токена подключение отклоняется, с токеном
`root:MilvusDemo123` проходит полный цикл (create → insert → flush → search → drop).

### Про LLM вне интернета (Ollama / LM Studio)

Attu в кластере видит `localhost` **как самого себя**, поэтому локальную модель надо адресовать
сетью хоста, а SSRF-защиту ослабить:

```yaml
# values/attu.yaml
allowPrivateModelEndpoints: true   # -> ATTU_SSRF_ALLOW_PRIVATE=true
```
base URL тогда, например, `http://<IP-хоста>:11434/v1` (Ollama) — и хост должен быть доступен из пода.

### Проверка работоспособности стенда

```powershell
kubectl -n milvus get pods
.\scripts\share-attu.ps1 -Tunnel none     # локальная ссылка + логин
# ожидаем: страница "Sign in - Attu" (HTTP 200)
```

> Экономия лимита Free-плана: правки только в документации/README пушите с
> `git push -o ci.skip` — пайплайн на них не запустится.

