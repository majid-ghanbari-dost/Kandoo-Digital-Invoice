$ErrorActionPreference = 'Stop'
$report = Join-Path $env:RUNNER_TEMP 'n04-pip-install-report.json'
$started = Get-Date
& $env:N04_PYTHON -m pip install --report $report -r scripts/n04-parisaocr-requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$elapsed = ((Get-Date) - $started).TotalSeconds
Write-Output ("N04_PIP_INSTALL_SECONDS={0:N3}" -f $elapsed)
