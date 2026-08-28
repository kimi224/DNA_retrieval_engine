$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Text.UTF8Encoding]::new($false)
$projectRoot = Split-Path -Parent $PSScriptRoot
$ruff = Join-Path $projectRoot ".venv\Scripts\ruff.exe"
$pytest = Join-Path $projectRoot ".venv\Scripts\pytest.exe"

Push-Location $projectRoot
try {
    & $ruff check src tests app.py scripts/stress_navigation.py scripts/stress_startup.py
    & $pytest --cov=dna_retrieval_engine --cov-report=term-missing --cov-fail-under=75
    node --check src/dna_retrieval_engine/resources/web/app.js
    node --check src/dna_retrieval_engine/resources/web/pages.js
    node --check src/dna_retrieval_engine/resources/web/bridge-client.js
    node --check src/dna_retrieval_engine/resources/web/ui-state.js
    node --check src/dna_retrieval_engine/resources/web/ui-actions.js
    node --check src/dna_retrieval_engine/resources/web/router.js

    $strictUtf8 = [Text.UTF8Encoding]::new($false, $true)
    $textExtensions = @(".py", ".js", ".css", ".html", ".json", ".md", ".txt", ".toml", ".ps1", ".spec")
    $textFiles = @(
        Get-ChildItem src, tests, docs, scripts, packaging -Recurse -File |
            Where-Object { $textExtensions -contains $_.Extension }
        Get-Item README.md, pyproject.toml, requirements.lock, .editorconfig, .gitattributes
    )
    foreach ($file in $textFiles) {
        $bytes = [IO.File]::ReadAllBytes($file.FullName)
        [void]$strictUtf8.GetString($bytes)
        if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
            throw "文本文件不应带 UTF-8 BOM：$($file.FullName)"
        }
    }
}
finally {
    Pop-Location
}
