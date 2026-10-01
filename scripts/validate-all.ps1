#Requires -Version 5.1
<#
.SYNOPSIS
  Локальная валидация репозитория (то же, что делает GitLab CI).

.DESCRIPTION
  Проверяет синтаксис PowerShell/Python, линтует и рендерит Helm-чарты.
  Полезно, если CI-раннер недоступен. Не требует кластера.

.EXAMPLE
  .\scripts\validate-all.ps1
#>
[CmdletBinding()]
param(
  [string]$MilvusChartVersion = "5.0.30",
  [string]$MilvusChartRepo = "https://zilliztech.github.io/milvus-helm/"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$fail = @()
function Step([string]$name, [scriptblock]$body) {
  Write-Host "==> $name" -ForegroundColor Cyan
  try { & $body; Write-Host "    OK" -ForegroundColor Green }
  catch { Write-Host "    FAIL: $($_.Exception.Message)" -ForegroundColor Red; $script:fail += $name }
}

Step "PowerShell syntax" {
  if (-not (Get-Command pwsh -ErrorAction SilentlyContinue)) { return }
  & pwsh -NoProfile -File (Join-Path $Root "scripts/ci-lint-powershell.ps1")
  if ($LASTEXITCODE -ne 0) { throw "pwsh lint failed" }
}

Step "Python compile" {
  if (-not (Get-Command python -ErrorAction SilentlyContinue)) { return }
  python -m compileall -q (Join-Path $Root "scripts")
  if ($LASTEXITCODE -ne 0) { throw "python compile failed" }
}

Step "helm lint chart/attu" {
  helm lint chart/attu | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "helm lint failed" }
}

Step "render Attu" {
  helm template attu chart/attu -f values/attu.yaml --set image.repository=zilliz/attu --set image.tag=v3.0.1 | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "helm template attu failed" }
}

Step "render Milvus ($MilvusChartVersion)" {
  helm repo add milvus $MilvusChartRepo --force-update | Out-Null
  helm template milvus milvus/milvus --version $MilvusChartVersion -f values/milvus.yaml | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "helm template milvus failed" }
}

Write-Host ""
if ($fail.Count -gt 0) {
  Write-Host "FAILED: $($fail -join ', ')" -ForegroundColor Red
  exit 1
}
Write-Host "Все проверки пройдены." -ForegroundColor Green