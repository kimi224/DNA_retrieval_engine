$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Text.UTF8Encoding]::new($false)
$projectRoot = Split-Path -Parent $PSScriptRoot
$pyinstaller = Join-Path $projectRoot ".venv\Scripts\pyinstaller.exe"
$spec = Join-Path $projectRoot "packaging\DNA_Retrieval_Engine.spec"

& (Join-Path $PSScriptRoot "check.ps1")

Push-Location $projectRoot
try {
    $env:DNA_BUILD_MODE = "onedir"
    & $pyinstaller --clean --noconfirm $spec

    $env:DNA_BUILD_MODE = "onefile"
    & $pyinstaller --clean --noconfirm $spec
}
finally {
    Remove-Item Env:\DNA_BUILD_MODE -ErrorAction SilentlyContinue
    Pop-Location
}

Write-Host "构建完成：dist\DNA_Retrieval_Engine_onedir 与 dist\DNA_Retrieval_Engine.exe"
