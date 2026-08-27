$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Text.UTF8Encoding]::new($false)
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $projectRoot ".venv"

if (-not (Test-Path -LiteralPath $venvPath)) {
    py -3.13 -m venv $venvPath
}

$python = Join-Path $venvPath "Scripts\python.exe"
& $python -c "import sys; assert sys.version_info[:2] == (3, 13), '需要 CPython 3.13'"
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $projectRoot "requirements.lock")
& $python -m pip install --no-deps -e $projectRoot
& $python -m pip check

Write-Host "环境已就绪：$venvPath"
