[CmdletBinding()]
param(
    [ValidateSet("Server", "LanEndpoint")]
    [string]$Mode = "Server",
    [ValidateRange(10, 3600)]
    [int]$IntervalSeconds = 30,
    [ValidatePattern("^[A-Za-z0-9._-]+$")]
    [string]$AgentId = "local-host",
    [string]$BackendUrl = "http://localhost:8000",
    [string]$AssetIp = "",
    [switch]$Once
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$AgentVersion = "1.0.0"

function Test-PrivateHost([string]$HostValue) {
    if ($HostValue -in @("localhost", "127.0.0.1", "::1")) { return $true }
    $parsed = $null
    if (-not [Net.IPAddress]::TryParse($HostValue, [ref]$parsed)) { return $false }
    $bytes = $parsed.GetAddressBytes()
    if ($bytes.Count -ne 4) { return $false }
    return $bytes[0] -eq 10 -or
        ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or
        ($bytes[0] -eq 192 -and $bytes[1] -eq 168)
}

function Get-PrivateAddress {
    if ($AssetIp) {
        if (-not (Test-PrivateHost $AssetIp) -or $AssetIp -in @("localhost", "127.0.0.1", "::1")) {
            throw "AssetIp must be a private RFC1918 IPv4 address."
        }
        return $AssetIp
    }
    $candidate = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object {
            (Test-PrivateHost $_.IPAddress) -and
            $_.IPAddress -notin @("127.0.0.1", "::1")
        } |
        Sort-Object InterfaceMetric |
        Select-Object -First 1
    if (-not $candidate) { throw "No private RFC1918 endpoint address was found." }
    return $candidate.IPAddress
}

function Read-Secret([string]$Prompt) {
    $secureValue = Read-Host $Prompt -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        $secureValue.Dispose()
    }
}

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
        collected_at = (Get-Date).ToUniversalTime().ToString("o")
        cpu_percent = $cpuPercent
        memory_percent = $memoryPercent
        disk_percent = $diskPercent
        process_count = @(Get-Process).Count
        uptime_seconds = $uptimeSeconds
        os_name = $operatingSystem.Caption
        os_version = $operatingSystem.Version
        agent_version = $AgentVersion
    }
}

$uri = [Uri]$BackendUrl
if ($uri.Scheme -notin @("http", "https")) { throw "BackendUrl must use http or https." }
if (-not (Test-PrivateHost $uri.Host)) {
    throw "The local monitor agent only sends to localhost or a private RFC1918 backend address."
}

$secretValue = $null
$headers = @{}
try {
    if ($Mode -eq "LanEndpoint") {
        $secretValue = Read-Secret "Paste the configured LAN endpoint agent token"
        if ([string]::IsNullOrWhiteSpace($secretValue)) { throw "A LAN endpoint agent token is required." }
        $headers = @{ "X-LAN-Agent-Token" = $secretValue }
        $endpointIp = Get-PrivateAddress
        $ipRecord = Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object IPAddress -eq $endpointIp | Select-Object -First 1
        $adapter = if ($ipRecord) {
            Get-NetAdapter -InterfaceIndex $ipRecord.InterfaceIndex -ErrorAction SilentlyContinue
        } else { $null }
        $os = Get-CimInstance Win32_OperatingSystem
        $registration = @{
            ip_address = $endpointIp
            mac_address = if ($adapter) { $adapter.MacAddress } else { $null }
            hostname = $env:COMPUTERNAME
            asset_type = "endpoint"
            os_name = $os.Caption
            os_version = $os.Version
            agent_version = $AgentVersion
        } | ConvertTo-Json -Compress
        $registered = Invoke-RestMethod -Method Post `
            -Uri ($BackendUrl.TrimEnd("/") + "/api/v1/monitoring/agent/register") `
            -Headers $headers -ContentType "application/json" -Body $registration
        $assetId = $registered.asset_id
        $endpoint = $BackendUrl.TrimEnd("/") + "/api/v1/monitoring/agent/telemetry"
        Write-Host "Endpoint registered. Sending basic resource telemetry every $IntervalSeconds seconds. Press Ctrl+C to stop."
    } else {
        $secretValue = Read-Secret "Paste a current local admin access token"
        if ([string]::IsNullOrWhiteSpace($secretValue)) { throw "An admin access token is required." }
        $headers = @{ Authorization = "Bearer $secretValue" }
        $endpoint = $BackendUrl.TrimEnd("/") + "/api/v1/monitoring/agent/ingest"
        $assetId = $null
        Write-Host "Sending server telemetry every $IntervalSeconds seconds. Press Ctrl+C to stop."
    }

    do {
        try {
            $sample = Get-LocalTelemetry
            if ($Mode -eq "LanEndpoint") {
                $payload = @{
                    asset_id = $assetId
                    collected_at = $sample.collected_at
                    cpu_percent = $sample.cpu_percent
                    memory_percent = $sample.memory_percent
                    disk_percent = $sample.disk_percent
                    uptime_seconds = $sample.uptime_seconds
                    os_name = $sample.os_name
                    os_version = $sample.os_version
                    agent_version = $sample.agent_version
                    metadata = @{ collection_mode = "manual" }
                } | ConvertTo-Json -Compress
            } else {
                $payload = @{
                    agent_id = $AgentId
                    platform = "windows"
                    collected_at = $sample.collected_at
                    cpu_percent = $sample.cpu_percent
                    memory_percent = $sample.memory_percent
                    disk_percent = $sample.disk_percent
                    process_count = $sample.process_count
                    uptime_seconds = $sample.uptime_seconds
                } | ConvertTo-Json -Compress
            }
            $response = Invoke-RestMethod -Method Post -Uri $endpoint `
                -Headers $headers -ContentType "application/json" -Body $payload
            Write-Host "Telemetry accepted at $($response.received_at)."
        } catch {
            Write-Warning "Telemetry was not accepted. Check LAN configuration, backend health, and the current token."
        }
        if (-not $Once) { Start-Sleep -Seconds $IntervalSeconds }
    } while (-not $Once)
} finally {
    $headers.Clear()
    $secretValue = $null
    Write-Host "Local monitor agent stopped. No persistence or autostart was configured."
}
