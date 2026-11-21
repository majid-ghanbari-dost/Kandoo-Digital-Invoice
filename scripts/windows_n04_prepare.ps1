$ErrorActionPreference = 'Stop'
$venv = Join-Path $env:RUNNER_TEMP 'n04-parisaocr-venv'
python -m venv $venv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$n04Python = Join-Path $venv 'Scripts/python.exe'
& $n04Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$baseline = Join-Path $env:RUNNER_TEMP 'n04-site-packages-before.json'
& $n04Python scripts/benchmark_n04_parisaocr.py --snapshot-site-packages $baseline
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$environmentLines = "N04_PYTHON=$n04Python`nN04_INSTALL_BASELINE=$baseline`n"
$utf8 = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::AppendAllText($env:GITHUB_ENV, $environmentLines, $utf8)
