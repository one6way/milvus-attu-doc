#Requires -Version 5.1
<#
.SYNOPSIS
  Открыть Attu в браузере — локально и с ДРУГИХ ПК (публичный туннель).

.DESCRIPTION
  Поднимает `kubectl port-forward` к сервису Attu и, при необходимости, публичный
  туннель. Благодаря туннелю Attu открывается с ЛЮБОГО ПК просто в браузере —
  без установки kubernetes, kubectl, helm и без доступа к кластеру.

  По умолчанию используется Cloudflare Quick Tunnel (аккаунт и домен не нужны),
  на выходе ссылка вида https://<случайные-слова>.trycloudflare.com.

  Скрипт ничего не деплоит (установку делает CI по тегу deploy-*) — он только
  открывает уже развёрнутый стенд. Остановить: Ctrl+C.

.PARAMETER Namespace
  Namespace со стендом (по умолчанию milvus).

.PARAMETER Service
  Имя сервиса Attu (по умолчанию attu).

.PARAMETER Port
  Локальный порт для port-forward (по умолчанию 3000).

.PARAMETER ContainerPort
  Порт Attu внутри пода (по умолчанию 3000).

.PARAMETER Tunnel
  none        - только локальный доступ (http://127.0.0.1:<Port>);
  cloudflared - публичная ссылка Cloudflare (по умолчанию, аккаунт не нужен);
  ngrok       - публичная ссылка ngrok (нужен настроенный authtoken).

.PARAMETER InstallCloudflared
  Разрешить установку cloudflared через winget, если его нет.

.EXAMPLE
  .\scripts\share-attu.ps1

.EXAMPLE
  .\scripts\share-attu.ps1 -Tunnel none

.EXAMPLE
  .\scripts\share-attu.ps1 -InstallCloudflared
#>
[CmdletBinding()]
param(
  [string]$Namespace = "milvus",
  [string]$Service = "attu",
  [int]$Port = 3000,
  [int]$ContainerPort = 3000,
  [ValidateSet("none", "cloudflared", "ngrok")]
  [string]$Tunnel = "cloudflared",
  [switch]$InstallCloudflared
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Info([string]$m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Ok([string]$m) { Write-Host "OK: $m" -ForegroundColor Green }
function Warn([string]$m) { Write-Host "!!  $m" -ForegroundColor Yellow }

function Need([string]$Cmd) {
  if (-not (Get-Command $Cmd -ErrorAction SilentlyContinue)) { throw "ERROR: не найдена команда: $Cmd" }
}

# Ждём, пока локальный порт начнёт принимать соединения.
function Wait-Port([int]$P, [int]$TimeoutSec = 30) {
  for ($i = 0; $i -lt ($TimeoutSec * 2); $i++) {
    $c = New-Object System.Net.Sockets.TcpClient
    try { $c.Connect("127.0.0.1", $P); $c.Close(); return $true }
    catch { if ($c) { $c.Close() }; Start-Sleep -Milliseconds 500 }
  }
  return $false
}

# Ищем в логе первое совпадение с regex (URL туннеля).
function Wait-Log([string]$Path, [string]$Pattern, [int]$TimeoutSec = 60) {
  for ($i = 0; $i -lt ($TimeoutSec * 2); $i++) {
    if (Test-Path $Path) {
      $txt = Get-Content -Path $Path -Raw -ErrorAction SilentlyContinue
      if ($txt) {
        $m = [regex]::Match($txt, $Pattern)
        if ($m.Success) { return $m.Value }
      }
    }
    Start-Sleep -Milliseconds 500
  }
  return $null
}

# Логин Attu 3.0 задаётся в values/attu.yaml (admin.user / admin.password).
function Get-AttuLogin {
  $f = Join-Path $Root "values\attu.yaml"
  $user = "admin"
  $pass = "см. values/attu.yaml (admin.user / admin.password)"
  if (Test-Path $f) {
    $txt = Get-Content -Path $f -Raw
    $mu = [regex]::Match($txt, '(?m)^\s*user:\s*"?([^"\r\n]+?)"?\s*$')
    $mp = [regex]::Match($txt, '(?m)^\s*password:\s*"?([^"\r\n]+?)"?\s*$')
    if ($mu.Success) { $user = $mu.Groups[1].Value }
    if ($mp.Success) { $pass = $mp.Groups[1].Value }
  }
  return @{ User = $user; Password = $pass }
}

Need kubectl

Info "Проверяю стенд: ns=$Namespace svc=$Service"
$null = kubectl -n $Namespace get svc $Service --no-headers 2>$null
if ($LASTEXITCODE -ne 0) {
  throw "ERROR: сервис $Service в ns $Namespace не найден. Сначала разверните стенд (CI-тег deploy-*)."
}

$logDir = Join-Path $env:TEMP ("attu-share-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$procs = @()
try {
  $pfOut = Join-Path $logDir "port-forward.out.log"
  $pfErr = Join-Path $logDir "port-forward.err.log"
  Info "port-forward 127.0.0.1:$Port -> svc/$Service (pod:$ContainerPort)"
  $pf = Start-Process kubectl -PassThru -WindowStyle Hidden `
    -ArgumentList @("-n", $Namespace, "port-forward", "svc/$Service", "$Port`:$ContainerPort") `
    -RedirectStandardOutput $pfOut -RedirectStandardError $pfErr
  $procs += $pf
  if (-not (Wait-Port $Port 30)) { throw "ERROR: port-forward не поднялся, см. $pfErr" }

  $url = "http://127.0.0.1:$Port"
  Ok "локально: $url"

  if ($Tunnel -eq "cloudflared") {
    if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue) -and $InstallCloudflared) {
      Info "Ставлю cloudflared через winget..."
      winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements | Out-Null
      $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    }
    if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
      $cfOut = Join-Path $logDir "cloudflared.out.log"
      $cfErr = Join-Path $logDir "cloudflared.err.log"
      Info "Поднимаю Cloudflare Quick Tunnel (аккаунт не нужен)..."
      $cf = Start-Process cloudflared -PassThru -WindowStyle Hidden `
        -ArgumentList @("tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:$Port") `
        -RedirectStandardOutput $cfOut -RedirectStandardError $cfErr
      $procs += $cf
      $pattern = "https://[a-z0-9-]+\.trycloudflare\.com"
      $pub = Wait-Log $cfErr $pattern 60
      if (-not $pub) { $pub = Wait-Log $cfOut $pattern 10 }
      if ($pub) { $url = $pub; Ok "публично (для других ПК): $pub" }
      else { Warn "URL туннеля не найден, смотрите $cfErr" }
    } else {
      Warn "cloudflared не найден. Запустите с -InstallCloudflared или: winget install --id Cloudflare.cloudflared -e"
    }
  } elseif ($Tunnel -eq "ngrok") {
    if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) {
      Warn "ngrok не найден: winget install --id Ngrok.Ngrok -e ; затем ngrok config add-authtoken <TOKEN>"
    } else {
      $ngOut = Join-Path $logDir "ngrok.out.log"
      $ngErr = Join-Path $logDir "ngrok.err.log"
      Info "Поднимаю ngrok..."
      $ng = Start-Process ngrok -PassThru -WindowStyle Hidden `
        -ArgumentList @("http", "$Port", "--log", "stdout") `
        -RedirectStandardOutput $ngOut -RedirectStandardError $ngErr
      $procs += $ng
      for ($i = 0; $i -lt 60; $i++) {
        try {
          $t = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
          $u = ($t.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1).public_url
          if ($u) { $url = $u; break }
        } catch { }
        Start-Sleep -Milliseconds 500
      }
      if ($url -like "https://*") { Ok "публично (для других ПК): $url" }
      else { Warn "ngrok не отдал URL, смотрите $ngErr" }
    }
  }

  $login = Get-AttuLogin
  Write-Host ""
  Write-Host "==============================================================" -ForegroundColor Cyan
  Write-Host "  Attu (открывать в браузере, можно с любого ПК):"
  Write-Host "    $url" -ForegroundColor Green
  Write-Host ""
  Write-Host "  Логин: $($login.User)"
  Write-Host "  Пароль: $($login.Password)"
  Write-Host ""
  Write-Host "  В Attu -> Connect: host = milvus , port = 19530"
  Write-Host "  Остановить туннель: Ctrl+C"
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
