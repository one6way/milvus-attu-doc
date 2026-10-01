#!/usr/bin/env pwsh
# CI: проверка синтаксиса всех PowerShell-скриптов в scripts/.
# Вызывается из .gitlab-ci.yml (job lint:powershell).
$ErrorActionPreference = "Stop"

$failed = $false
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Get-ChildItem -Path (Join-Path $root "*.ps1") | ForEach-Object {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$errors)
    if ($errors -and $errors.Count -gt 0) {
        Write-Host "FAIL: $($_.Name)"
        $errors | ForEach-Object { Write-Host ("  " + $_.Message) }
        $failed = $true
    } else {
        Write-Host "OK: $($_.Name)"
    }
}

if ($failed) {
    Write-Error "PowerShell syntax errors found"
    exit 1
}
Write-Host "PowerShell syntax OK"