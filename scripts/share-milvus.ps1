#Requires -Version 5.1
<#
.SYNOPSIS
  Дать доступ к Milvus (pymilvus / SDK / Attu) — локально и с ДРУГИХ ПК.

.DESCRIPTION
  Поднимает `kubectl port-forward` к сервису Milvus (порт 19530) и, при
  необходимости, публичный TCP-туннель ngrok. После этого с другого ПК можно
  подключаться к Milvus напрямую:

    from pymilvus import MilvusClient
    c = MilvusClient(uri="http://<host>:<port>", token="root:<пароль>")

  Тот же host/port используется в Attu (Connect) и в scripts/vectorize_docx.py
  (--host/--port/--token).

  ВАЖНО: перед публикацией порта включите авторизацию Milvus
  (values/milvus.yaml -> extraConfigFiles -> common.security.authorizationEnabled).
  Без авторизации открытый 19530 доступен всем: чтение, запись, удаление коллекций.

  Скрипт ничего не деплоит (установку делает CI по тегу deploy-*).
  Остановить: Ctrl+C.

.PARAMETER Namespace
  Namespace со стендом (по умолчанию milvus).

.PARAMETER Service
  Имя сервиса Milvus (по умолчанию milvus).

.PARAMETER Port
  Локальный порт для port-forward (по умолчанию 19530).

.PARAMETER ContainerPort
  Порт Milvus внутри пода (по умолчанию 19530).

.PARAMETER Tunnel
  none  - только локально/LAN: подойдёт для Tailscale, VPN или своей сети;
  ngrok - публичный TCP-адрес ngrok (нужен аккаунт: ngrok config add-authtoken).

.PARAMETER InstallNgrok
  Разрешить установку ngrok через winget, если его нет.

.EXAMPLE
  .\scripts\share-milvus.ps1 -Tunnel none

.EXAMPLE
  .\scripts\share-milvus.ps1 -Tunnel ngrok
#>
[CmdletBinding()]
param(
  [string]$Namespace = "milvus",
  [string]$Service = "milvus",
  [int]$Port = 19530,
  [int]$ContainerPort = 19530,
  [ValidateSet("none", "ngrok")]
  [string]$Tunnel = "ngrok",
  [switch]$InstallNgrok
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Info([string]$m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Ok([string]$m) { Write-Host "OK: $m" -ForegroundColor Green }
function Warn([string]$m) { Write-Host "!!  $m" -ForegroundColor Yellow }

function Need([string]$Cmd) {
  if (-not (Get-Command $Cmd -ErrorAction SilentlyContinue)) { throw "ERROR: не найдена команда: $Cmd" }
}

function Wait-Port([int]$P, [int]$TimeoutSec = 30) {
  for ($i = 0; $i -lt ($TimeoutSec * 2); $i++) {
    $c = New-Object System.Net.Sockets.TcpClient
    try { $c.Connect("127.0.0.1", $P); $c.Close(); return $true }
    catch { if ($c) { $c.Close() }; Start-Sleep -Milliseconds 500 }
  }
  return $false
}

# Пароль root берём из values/milvus.yaml (extraConfigFiles -> defaultRootPassword).
function Get-MilvusRootPassword {
  $f = Join-Path $Root "values\milvus.yaml"
  if (Test-Path $f) {
    $txt = Get-Content -Path $f -Raw
    $m = [regex]::Match($txt, '(?m)^\s*defaultRootPassword:\s*"?([^"\r\n#]+?)"?\s*$')
    if ($m.Success) { return $m.Groups[1].Value.Trim() }
  }
  return "Milvus"
}

Need kubectl

Info "Проверяю стенд: ns=$Namespace svc=$Service"
$null = kubectl -n $Namespace get svc $Service --no-headers 2>$null
if ($LASTEXITCODE -ne 0) {
  throw "ERROR: сервис $Service в ns $Namespace не найден. Сначала разверните стенд (CI-тег deploy-*)."
}

$logDir = Join-Path $env:TEMP ("milvus-share-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$procs = @()
try {
  $pfErr = Join-Path $logDir "port-forward.err.log"
  Info "port-forward 127.0.0.1:$Port -> svc/$Service (pod:$ContainerPort)"
  $pf = Start-Process kubectl -PassThru -WindowStyle Hidden `
    -ArgumentList @("-n", $Namespace, "port-forward", "svc/$Service", "$Port`:$ContainerPort") `
    -RedirectStandardOutput (Join-Path $logDir "port-forward.out.log") -RedirectStandardError $pfErr
  $procs += $pf
  if (-not (Wait-Port $Port 30)) { throw "ERROR: port-forward не поднялся, см. $pfErr" }

  $host_ = "127.0.0.1"
  $port_ = $Port
  Ok "локально: ${host_}:${port_}"

  if ($Tunnel -eq "ngrok") {
    if (-not (Get-Command ngrok -ErrorAction SilentlyContinue) -and $InstallNgrok) {
      Info "Ставлю ngrok через winget..."
      winget install --id Ngrok.Ngrok -e --accept-source-agreements --accept-package-agreements | Out-Null
      $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    }
    if (Get-Command ngrok -ErrorAction SilentlyContinue) {
      $ngErr = Join-Path $logDir "ngrok.err.log"
      Info "Поднимаю ngrok tcp ($Port)..."
      $ng = Start-Process ngrok -PassThru -WindowStyle Hidden `
        -ArgumentList @("tcp", "$Port", "--log", "stdout") `
        -RedirectStandardOutput (Join-Path $logDir "ngrok.out.log") -RedirectStandardError $ngErr
      $procs += $ng
      $pub = $null
      for ($i = 0; $i -lt 60; $i++) {
        try {
          $t = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
          $u = ($t.tunnels | Where-Object { $_.proto -eq "tcp" } | Select-Object -First 1).public_url
          if ($u) { $pub = $u; break }
        } catch { }
        Start-Sleep -Milliseconds 500
      }
      if ($pub) {
        $hp = $pub -replace '^tcp://', ''
        $host_ = $hp.Split(':')[0]
        $port_ = $hp.Split(':')[1]
        Ok "публично (для других ПК): ${host_}:${port_}"
      } else {
        Warn "ngrok не отдал TCP-адрес, смотрите $ngErr (нужен: ngrok config add-authtoken <TOKEN>)"
      }
    } else {
      Warn "ngrok не найден: winget install --id Ngrok.Ngrok -e ; затем ngrok config add-authtoken <TOKEN>"
    }
  } elseif ($Tunnel -eq "none") {
    Info "Туннель не поднимаю. Для другого ПК используйте адрес вашего ПК в LAN/Tailscale/VPN."
  }

  $pw = Get-MilvusRootPassword
  Write-Host ""
  Write-Host "==============================================================" -ForegroundColor Cyan
  Write-Host "  Milvus для pymilvus / SDK:"
  Write-Host "    host=$host_  port=$port_" -ForegroundColor Green
  Write-Host ""
  Write-Host "  from pymilvus import MilvusClient"
  Write-Host "  c = MilvusClient(uri=`"http://$host_`:$port_`", token=`"root:$pw`")"
  Write-Host ""
  Write-Host "  В Attu -> Connect: host=$host_ , port=$port_ , User=root , Password=$pw"
  Write-Host "  Остановить: Ctrl+C"
  Write-Host "==============================================================" -ForegroundColor Cyan
  Write-Host ""

  Wait-Process -Id ($procs | ForEach-Object { $_.Id })
} finally {
  foreach ($p in $procs) {
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
  }
  Remove-Item -Recurse -Force $logDir -ErrorAction SilentlyContinue
  Info "Остановлено (локальный порт $Port закрыт)."
}
