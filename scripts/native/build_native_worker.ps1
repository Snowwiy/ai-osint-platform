$ErrorActionPreference = 'Stop'
& python (Join-Path $PSScriptRoot 'build.py') worker
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
