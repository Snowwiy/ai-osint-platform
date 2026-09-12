[CmdletBinding()]
param(
    [ValidateSet("ServerHost", "BackendHost", "Server", "LanEndpoint")]
    [string]$Mode = "ServerHost",
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
$AgentVersion = "1.1.0"

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

function Get-AdapterForAddress([string]$Address) {
    $ipRecord = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object IPAddress -eq $Address | Select-Object -First 1
    if (-not $ipRecord) { return $null }
    return Get-NetAdapter -InterfaceIndex $ipRecord.InterfaceIndex -ErrorAction SilentlyContinue
}

function ConvertTo-NormalizedMac([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return $null }
    $normalized = $Value.Trim().Replace("-", ":").ToUpperInvariant()
    if ($normalized -notmatch '^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$') { return $null }
    return $normalized
}

function Get-SafeHostNeighborObservations([string]$HostAddress) {
    if (-not (Test-PrivateHost $HostAddress)) { return @() }
    $octets = $HostAddress.Split(".")
    if ($octets.Count -ne 4) { return @() }
    $prefix = "$($octets[0]).$($octets[1]).$($octets[2])."
    $observedAt = (Get-Date).ToUniversalTime().ToString("o")
    try {
        return @(Get-NetNeighbor -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object {
                $_.IPAddress.StartsWith($prefix) -and
                $_.IPAddress -ne $HostAddress -and
                $_.IPAddress -notmatch '\.(0|255)$' -and
                (Test-PrivateHost $_.IPAddress)
            } |
            Sort-Object IPAddress -Unique |
            Select-Object -First 256 |
            ForEach-Object {
                $neighborState = if ($_.State) { ([string]$_.State).ToLowerInvariant() } else { "unknown" }
                if ($neighborState -notin @("reachable", "stale", "delay", "probe", "permanent", "unreachable", "incomplete")) {
                    $neighborState = "unknown"
                }
                @{
                    ip_address = $_.IPAddress
                    mac_address = ConvertTo-NormalizedMac $_.LinkLayerAddress
                    interface_name = if ($_.InterfaceAlias) { [string]$_.InterfaceAlias } else { $null }
                    state = $neighborState
                    observed_at = $observedAt
                    source = "host_neighbor_table"
                }
            })
    } catch {
        return @()
    }
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
    $firewallStatus = "unavailable"
    try {
        $profiles = @(Get-NetFirewallProfile -ErrorAction Stop)
        if ($profiles.Count) {
            $firewallStatus = if (@($profiles | Where-Object { -not $_.Enabled }).Count) { "disabled" } else { "enabled" }
        }
    } catch { $firewallStatus = "unavailable" }
    $antivirusStatus = "unavailable"
    try {
        $defender = Get-MpComputerStatus -ErrorAction Stop
        $antivirusStatus = if ($defender.AntivirusEnabled -and $defender.RealTimeProtectionEnabled) { "enabled" } else { "disabled" }
    } catch { $antivirusStatus = "unavailable" }
    $hotfixes = @()
    try { $hotfixes = @(Get-HotFix -ErrorAction Stop | Where-Object InstalledOn | Sort-Object InstalledOn -Descending) } catch { $hotfixes = @() }
    $latestPatch = if ($hotfixes.Count) { $hotfixes[0].InstalledOn } else { $null }
    $patchStatus = if (-not $latestPatch) { "unknown" } elseif ($latestPatch -lt (Get-Date).AddDays(-45)) { "stale" } else { "current" }
    $pendingFileRename = Get-ItemProperty `
        -LiteralPath "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager" `
        -Name PendingFileRenameOperations `
        -ErrorAction SilentlyContinue
    $pendingReboot = (Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired") -or
        ($null -ne $pendingFileRename)
    $listeningPorts = @()
    try {
        $listeningPorts = @(Get-NetTCPConnection -State Listen -ErrorAction Stop |
            Select-Object -ExpandProperty LocalPort -Unique | Sort-Object | Select-Object -First 64)
    } catch { $listeningPorts = @() }
    return @{
        collected_at = (Get-Date).ToUniversalTime().ToString("o")
        cpu_percent = $cpuPercent
        memory_percent = $memoryPercent
        disk_percent = $diskPercent
        process_count = @(Get-Process).Count
        uptime_seconds = $uptimeSeconds
        os_name = $operatingSystem.Caption
        os_version = $operatingSystem.Version
        os_build = $operatingSystem.BuildNumber
        agent_version = $AgentVersion
        disk_free_gb = if ($drive) { [Math]::Round([double]$drive.FreeSpace / 1GB, 2) } else { $null }
        firewall_status = $firewallStatus
        antivirus_status = $antivirusStatus
        patch_status = $patchStatus
        latest_patch_date = if ($latestPatch) { $latestPatch.ToString("yyyy-MM-dd") } else { $null }
        recent_hotfix_count = @($hotfixes | Where-Object { $_.InstalledOn -ge (Get-Date).AddDays(-90) }).Count
        pending_reboot = $pendingReboot
        listening_tcp_ports = $listeningPorts
    }
}

$uri = [Uri]$BackendUrl
if ($uri.Scheme -notin @("http", "https")) { throw "BackendUrl must use http or https." }
if (-not (Test-PrivateHost $uri.Host)) {
    throw "The local monitor agent only sends to localhost or a private RFC1918 backend address."
}

$secretValue = $null
$headers = @{}
$hostAddress = $null
$hostAdapter = $null
try {
    if ($Mode -eq "LanEndpoint") {
        $secretValue = Read-Secret "Paste the configured LAN endpoint agent token"
        if ([string]::IsNullOrWhiteSpace($secretValue)) { throw "A LAN endpoint agent token is required." }
        $headers = @{ "X-LAN-Agent-Token" = $secretValue }
        $endpointIp = Get-PrivateAddress
        $adapter = Get-AdapterForAddress $endpointIp
        $os = Get-CimInstance Win32_OperatingSystem
        $registration = @{
            ip_address = $endpointIp
            mac_address = if ($adapter) { $adapter.MacAddress } else { $null }
            hostname = $env:COMPUTERNAME
            asset_type = "lan_endpoint"
            os_name = $os.Caption
            os_version = $os.Version
            agent_version = $AgentVersion
            capabilities = @("basic_telemetry", "os_basics", "security_posture", "patch_awareness", "listening_ports")
        } | ConvertTo-Json -Compress
        $registered = Invoke-RestMethod -Method Post `
            -Uri ($BackendUrl.TrimEnd("/") + "/api/v1/monitoring/agent/register") `
            -Headers $headers -ContentType "application/json" -Body $registration
        $assetId = $registered.asset_id
        $endpoint = $BackendUrl.TrimEnd("/") + "/api/v1/monitoring/agent/telemetry"
        Write-Host "Endpoint asset registered for $endpointIp. Sending approved telemetry every $IntervalSeconds seconds. Press Ctrl+C to stop."
    } else {
        $secretValue = Read-Secret "Paste a current local admin access token"
        if ([string]::IsNullOrWhiteSpace($secretValue)) { throw "An admin access token is required." }
        $headers = @{ Authorization = "Bearer $secretValue" }
        $endpoint = $BackendUrl.TrimEnd("/") + "/api/v1/monitoring/agent/ingest"
        $assetId = $null
        $agentRole = if ($Mode -eq "ServerHost") { "server_host" } else { "backend_host" }
        if ($Mode -eq "ServerHost") {
            $hostAddress = Get-PrivateAddress
            $hostAdapter = Get-AdapterForAddress $hostAddress
        }
        Write-Host "Sending $Mode telemetry every $IntervalSeconds seconds. Press Ctrl+C to stop."
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
                    os_build = $sample.os_build
                    agent_version = $sample.agent_version
                    disk_free_gb = $sample.disk_free_gb
                    firewall_status = $sample.firewall_status
                    antivirus_status = $sample.antivirus_status
                    patch_status = $sample.patch_status
                    latest_patch_date = $sample.latest_patch_date
                    recent_hotfix_count = $sample.recent_hotfix_count
                    pending_reboot = $sample.pending_reboot
                    listening_tcp_ports = $sample.listening_tcp_ports
                    metadata = @{ collection_mode = "manual" }
                } | ConvertTo-Json -Compress
            } else {
                $neighbors = if ($Mode -eq "ServerHost") {
                    @(Get-SafeHostNeighborObservations $hostAddress)
                } else { @() }
                $payload = @{
                    agent_id = $AgentId
                    platform = "windows"
                    agent_role = $agentRole
                    hostname = $env:COMPUTERNAME
                    ip_address = $hostAddress
                    mac_address = if ($hostAdapter) { ConvertTo-NormalizedMac $hostAdapter.MacAddress } else { $null }
                    os_name = $sample.os_name
                    os_version = $sample.os_version
                    os_build = $sample.os_build
                    collected_at = $sample.collected_at
                    cpu_percent = $sample.cpu_percent
                    memory_percent = $sample.memory_percent
                    disk_percent = $sample.disk_percent
                    process_count = $sample.process_count
                    uptime_seconds = $sample.uptime_seconds
                    listening_tcp_ports = $sample.listening_tcp_ports
                    neighbor_observations = $neighbors
                } | ConvertTo-Json -Compress
            }
            $response = Invoke-RestMethod -Method Post -Uri $endpoint `
                -Headers $headers -ContentType "application/json" -Body $payload
            if ($Mode -eq "ServerHost") {
                Write-Host "Telemetry accepted; host metrics sent; LAN asset registered: $($response.lan_asset_registered); neighbor observations sent: $($response.neighbor_observations_accepted); next heartbeat in ${IntervalSeconds}s."
            } elseif ($Mode -eq "LanEndpoint") {
                Write-Host "Heartbeat accepted for LAN endpoint $endpointIp; telemetry is fresh; next heartbeat in ${IntervalSeconds}s."
            } else {
                Write-Host "Telemetry accepted at $($response.received_at)."
            }
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
