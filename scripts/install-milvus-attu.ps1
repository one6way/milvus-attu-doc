#Requires -Version 5.1
<#
.SYNOPSIS
  Установка последних Milvus (3.0) + Attu (3.0.1) в текущий Kubernetes-контекст.

.DESCRIPTION
  Один скрипт: Milvus 3.0 (официальный Helm-чарт zilliztech milvus-helm) + Attu 3.0.1.
  Работает с любым контекстом kubectl (Docker Desktop, kind, ...). Требуется интернет
  (официальные образы milvusdb/milvus, milvusdb/etcd, milvusdb/minio, zilliz/attu).

  Milvus ставится в режиме standalone с messageQueue=woodpecker (встроенный WAL),
  поэтому Pulsar/Kafka не нужны. Параметры заданы в values/values-milvus-3.0-desktop.yaml.

.PARAMETER Namespace
  Namespace для обоих релизов (по умолчанию milvus).

.PARAMETER MilvusChartVersion
  Версия Helm-чарта Milvus (по умолчанию 5.0.30 -> образ milvusdb/milvus:v3.0.1).

.PARAMETER AttuImage
  Образ Attu (по умолчанию zilliz/attu:v3.0.1).

.PARAMETER DryRun
  Только отрендерить чарты через `helm template` (проверка values), без установки.

.EXAMPLE
  .\scripts\install-milvus-attu.ps1
.EXAMPLE
  .\scripts\install-milvus-attu.ps1 -DryRun
.EXAMPLE
  .\scripts\install-milvus-attu.ps1 -Namespace milvus -AttuPort 13000
#>
[CmdletBinding()]
param(
  [string]$Namespace = "milvus",
  [string]$MilvusChartVersion = "5.0.30",
  [string]$AttuImage = "zilliz/attu:v3.0.1",
  [string]$MilvusValues = "",
  [string]$AttuValues = "",
  [int]$TimeoutMinutes = 15,
  [int]$AttuPort = 13000,
  [switch]$SkipRepoUpdate,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RepoName = "milvus"
$RepoUrl = "https://zilliztech.github.io/milvus-helm/"
$MilvusRelease = "milvus"
$AttuRelease = "attu"

function Need([string]$Cmd) {
  if (-not (Get-Command $Cmd -ErrorAction SilentlyContinue)) { throw "ERROR: не найдена команда: $Cmd" }
}
function Info([string]$m) { Write-Host "==> $m" -ForegroundColor Cyan }

Need docker
Need kubectl
Need helm

# --- values по умолчанию ---
if (-not $MilvusValues) { $MilvusValues = Join-Path $Root "values\milvus.yaml" }
if (-not $AttuValues) { $AttuValues = Join-Path $Root "values\attu.yaml" }
$AttuChart = Join-Path $Root "chart\attu"
foreach ($f in @($MilvusValues, $AttuValues)) {
  if (-not (Test-Path $f)) { throw "ERROR: не найден values-файл: $f" }
}
if (-not (Test-Path (Join-Path $AttuChart "Chart.yaml"))) { throw "ERROR: не найден chart/attu: $AttuChart" }

# --- образ Attu: разделяем repository:tag ---
$AttuRepo = $AttuImage
$AttuTag = "latest"
if ($AttuImage.Contains(":")) {
  $i = $AttuImage.LastIndexOf(":")
  $AttuRepo = $AttuImage.Substring(0, $i)
  $AttuTag = $AttuImage.Substring($i + 1)
}

# --- окружение ---
$ctx = (kubectl config current-context 2>$null)
Info "kube-context: $ctx"
if (-not $ctx) { throw "ERROR: не задан контекст kubectl (ожидается docker-desktop или kind)." }

$null = docker info 2>&1
if ($LASTEXITCODE -ne 0) { throw "ERROR: Docker daemon недоступен." }

# --- helm repo ---
Info "helm repo: $RepoName -> $RepoUrl"
helm repo add $RepoName $RepoUrl --force-update | Out-Null
if (-not $SkipRepoUpdate) { helm repo update $RepoName | Out-Null }

# --- аргументы ---
$milvusArgs = @(
  "upgrade", "--install", $MilvusRelease, "$RepoName/milvus",
  "--version", $MilvusChartVersion,
  "--namespace", $Namespace, "--create-namespace",
  "-f", $MilvusValues
)
$attuArgs = @(
  "upgrade", "--install", $AttuRelease, $AttuChart,
  "--namespace", $Namespace,
  "-f", $AttuValues,
  "--set", "image.repository=$AttuRepo",
  "--set", "image.tag=$AttuTag"
)

if ($DryRun) {
  Info "[DryRun] render Milvus ($MilvusChartVersion)"
  helm template $MilvusRelease "$RepoName/milvus" --version $MilvusChartVersion -n $Namespace -f $MilvusValues | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "ERROR: helm template milvus завершился с ошибкой." }
  Info "[DryRun] render Attu ($AttuImage)"
  helm template $AttuRelease $AttuChart -n $Namespace -f $AttuValues --set "image.repository=$AttuRepo" --set "image.tag=$AttuTag" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "ERROR: helm template attu завершился с ошибкой." }
  Info "[DryRun] OK: оба чарта рендерятся без ошибок."
  return
}

# --- установка Milvus ---
Info "Milvus $MilvusChartVersion -> namespace $Namespace (timeout ${TimeoutMinutes}m)"
helm @milvusArgs --wait --timeout "${TimeoutMinutes}m"
if ($LASTEXITCODE -ne 0) { throw "ERROR: helm install milvus завершился с ошибкой." }

# --- установка Attu ---
Info "Attu $AttuImage -> namespace $Namespace"
helm @attuArgs --wait --timeout "5m"
if ($LASTEXITCODE -ne 0) { throw "ERROR: helm install attu завершился с ошибкой." }

Info "Состояние:"
kubectl -n $Namespace get pods,svc

Write-Host ""
Info "Готово."
Write-Host "  Открыть Attu:  kubectl -n $Namespace port-forward svc/$AttuRelease ${AttuPort}:3000"
Write-Host "                 затем http://127.0.0.1:$AttuPort"
Write-Host "  В форме Attu:  адрес Milvus = milvus:19530  (НЕ 127.0.0.1!)"
Write-Host "  Прямой порт Milvus: kubectl -n $Namespace port-forward svc/milvus 19530:19530"