[CmdletBinding()]
param(
    [ValidateRange(10, 3600)]
    [int]$IntervalSeconds = 30,
    [ValidatePattern("^[A-Za-z0-9._-]+$")]
    [string]$AgentId = "local-host",
    [string]$BackendUrl = "http://localhost:8000",
    [switch]$Once
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$uri = [Uri]$BackendUrl
if ($uri.Scheme -ne "http" -and $uri.Scheme -ne "https") {
    throw "BackendUrl must use http or https."
}
if ($uri.Host -notin @("localhost", "127.0.0.1", "::1")) {
    throw "Local monitor agent only sends telemetry to localhost."
}

$secureToken = Read-Host "Paste a current local admin access token" -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
$accessToken = $null
try {
    $accessToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
}
if ([string]::IsNullOrWhiteSpace($accessToken)) {
    throw "An admin access token is required."
}

$endpoint = $BackendUrl.TrimEnd("/") + "/api/v1/monitoring/agent/ingest"
$headers = @{ Authorization = "Bearer $accessToken" }

function Get-LocalTelemetry {
    $processors = @(Get-CimInstance Win32_Processor)
    $cpuValues = @($processors | ForEach-Object { [double]$_.LoadPercentage })
    $cpuPercent = if ($cpuValues.Count) {
        [Math]::Round(($cpuValues | Measure-Object -Average).Average, 1)
    } else { $null }

    $operatingSystem = Get-CimInstance Win32_OperatingSystem
    $totalMemory = [double]$operatingSystem.TotalVisibleMemorySize
    $freeMemory = [double]$operatingSystem.FreePhysicalMemory
    $memoryPercent = if ($totalMemory -gt 0) {
        [Math]::Round((($totalMemory - $freeMemory) / $totalMemory) * 100, 1)
    } else { $null }

    $driveId = if ($env:SystemDrive) { $env:SystemDrive } else { "C:" }
    $drive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$driveId'"
    $diskPercent = if ($drive -and [double]$drive.Size -gt 0) {
        [Math]::Round((([double]$drive.Size - [double]$drive.FreeSpace) / [double]$drive.Size) * 100, 1)
    } else { $null }

    $bootTime = $operatingSystem.LastBootUpTime
    $uptimeSeconds = if ($bootTime) {
        [Math]::Max(0, [int64]((Get-Date) - $bootTime).TotalSeconds)
    } else { $null }

    return @{
        agent_id = $AgentId
        platform = "windows"
        collected_at = (Get-Date).ToUniversalTime().ToString("o")
        cpu_percent = $cpuPercent
        memory_percent = $memoryPercent
        disk_percent = $diskPercent
        process_count = @(Get-Process).Count
        uptime_seconds = $uptimeSeconds
    }
}

try {
    Write-Host "Sending local-only telemetry every $IntervalSeconds seconds. Press Ctrl+C to stop."
    do {
        try {
            $payload = Get-LocalTelemetry | ConvertTo-Json -Compress
            $response = Invoke-RestMethod -Method Post -Uri $endpoint `
                -Headers $headers -ContentType "application/json" -Body $payload
            Write-Host "Telemetry accepted at $($response.received_at)."
        } catch {
            Write-Warning "Telemetry was not accepted. Check backend health and refresh the admin token."
        }
        if (-not $Once) { Start-Sleep -Seconds $IntervalSeconds }
    } while (-not $Once)
} finally {
    $headers.Authorization = "Bearer [CLEARED]"
    $accessToken = $null
    $secureToken.Dispose()
    Write-Host "Local monitor agent stopped."
}
