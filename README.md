# Milvus + Attu (Kubernetes)

Минимальный репозиторий для развёртывания **Milvus 3.0** и **Attu 3.0** в Kubernetes
(`docker-desktop`, kind, любой кластер) и для загрузки в Milvus текста из документов Word.

Состав — **только необходимое**: нет образов, дампов, бэкапов и сторонних проектов.

## Что внутри

| Путь | Назначение |
|------|------------|
| `chart/attu/` | Helm-чарт Attu (наш, non-root, порт 3000) |
| `values/milvus.yaml` | Values Milvus 3.0: standalone, messageQueue=woodpecker, StorageClass `standard`, ClusterIP |
| `values/attu.yaml` | Values Attu: образ `zilliz/attu:v3.0.1`, адрес Milvus `milvus:19530` |
| `scripts/install-milvus-attu.ps1` | **Один скрипт**: ставит Milvus (официальный чарт) + Attu |
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
| deploy | `deploy:milvus` | Установка Milvus | **self-hosted** |
| deploy | `deploy:attu` | Установка Attu | **self-hosted** |
| verify | `verify:stack` | Проверка установленного ПО | **self-hosted** |

Автоматические джобы (lint/package/check/validate) работают на shared-раннере GitLab.com
и не требуют доступа к кластеру. Джобы `deploy:*` и `verify:stack` вынесены отдельно,
т.к. **кластер в CI эфемерный**, а «установить Milvus → установить Attu → проверить»
должно идти на **одном и том же** кластере — поэтому они выполняются на self-hosted раннере.

### Требование: активный раннер

На GitLab.com у нового бесплатного аккаунта shared-раннеры неактивны (статус `paused`).
Лечится так:

1. GitLab → (аватар) → **Edit profile → Account** → верификация личности.
2. Проект → **Settings → CI/CD → Runners** → включить shared runners.

### Self-hosted раннер для deploy/verify

Чтобы джобы установки работали, зарегистрируйте раннер на машине с кластером
(Docker Desktop + kubectl + helm):

1. Проект → **Settings → CI/CD → Runners → New project runner**, tag: **`milvus-k8s`**.
2. Установить и запустить `gitlab-runner` (executor: **shell**, на Windows достаточно
   установленных `kubectl`/`helm`; kubeconfig — из Docker Desktop).
3. Запуск пайплайна с установкой: **Run pipeline** → переменная **`DEPLOY=true`**.

Джобы `deploy/verify` не создаются в обычном пайплайне (см. `rules`), поэтому без
раннера пайплайн остаётся зелёным.

### Проверка без раннера (локально)

Тот же набор статических проверок:

```powershell
.\scripts\validate-all.ps1
```
