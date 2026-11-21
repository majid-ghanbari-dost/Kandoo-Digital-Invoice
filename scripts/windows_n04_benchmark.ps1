$ErrorActionPreference = 'Stop'
$json = Join-Path $env:RUNNER_TEMP 'n04-name-suggestions.json'
$markdown = Join-Path $env:RUNNER_TEMP 'n04-name-suggestions.md'
$errorJson = Join-Path $env:RUNNER_TEMP 'n04-name-suggestions-error.json'
& $env:N04_PYTHON scripts/benchmark_n04_parisaocr.py `
  --repo-root . `
  --install-baseline $env:N04_INSTALL_BASELINE `
  --output-json $json `
  --output-markdown $markdown `
  --error-json $errorJson
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
