$ErrorActionPreference = 'Stop'
& python (Join-Path $PSScriptRoot 'validate.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
