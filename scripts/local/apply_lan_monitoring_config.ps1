[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Test-RavenTechRepositoryRoot([string]$Candidate) {
    if ([string]::IsNullOrWhiteSpace($Candidate)) { return $null }
    try {
        $root = (Resolve-Path -LiteralPath $Candidate -ErrorAction Stop).Path
    } catch {
        return $null
    }
    $required = @(
        "docker-compose.yml",
        "pyproject.toml",
        "frontend/package.json",
        "desktop/package.json",
        "scripts/local/apply_lan_monitoring_config.ps1"
    )
    foreach ($relative in $required) {
        if (-not (Test-Path -LiteralPath ([IO.Path]::Combine($root, $relative)) -PathType Leaf)) {
            return $null
        }
    }
    if (-not (Test-Path -LiteralPath ([IO.Path]::Combine($root, "backend/app")) -PathType Container)) {
        return $null
    }
    return $root
}

function Resolve-RavenTechRepositoryRoot {
    $candidates = [Collections.Generic.List[string]]::new()
    if (-not [string]::IsNullOrWhiteSpace($env:RAVENTECH_VALIDATED_PROJECT_ROOT)) {
        $candidates.Add($env:RAVENTECH_VALIDATED_PROJECT_ROOT)
    }
    if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        $candidates.Add([IO.Path]::GetFullPath([IO.Path]::Combine($PSScriptRoot, "../..")))
    }
    if (-not [string]::IsNullOrWhiteSpace($PSCommandPath)) {
        $scriptDirectory = [IO.Path]::GetDirectoryName($PSCommandPath)
        if (-not [string]::IsNullOrWhiteSpace($scriptDirectory)) {
            $candidates.Add([IO.Path]::GetFullPath([IO.Path]::Combine($scriptDirectory, "../..")))
        }
    }
    $currentPath = (Get-Location).Path
    if (-not [string]::IsNullOrWhiteSpace($currentPath)) { $candidates.Add($currentPath) }
    foreach ($candidate in $candidates) {
        $resolved = Test-RavenTechRepositoryRoot $candidate
        if ($resolved) { return $resolved }
    }
    throw "RavenTech repository root could not be resolved. Bind a validated project path and retry."
}

function ConvertTo-AuthorizedPrivateCidr([string]$Value) {
    if ($Value -notmatch '^([^/]+)/([0-9]{1,2})$') {
        throw "The fixed LAN CIDR is invalid."
    }
    $address = $null
    if (-not [Net.IPAddress]::TryParse($Matches[1], [ref]$address)) {
        throw "The fixed LAN CIDR is invalid."
    }
    $bytes = $address.GetAddressBytes()
    $prefix = [int]$Matches[2]
    $private = $bytes.Count -eq 4 -and (
        $bytes[0] -eq 10 -or
        ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or
        ($bytes[0] -eq 192 -and $bytes[1] -eq 168)
    )
    if (-not $private) { throw "Public CIDRs are not permitted." }
    if ($prefix -lt 24 -or $prefix -gt 32) {
        throw "The fixed LAN CIDR exceeds the 256-host safety limit."
    }
    $network = for ($index = 0; $index -lt 4; $index++) {
        $remaining = $prefix - ($index * 8)
        $mask = if ($remaining -ge 8) { 255 } elseif ($remaining -le 0) { 0 } else { 256 - [Math]::Pow(2, 8 - $remaining) }
        [int]$bytes[$index] -band [int]$mask
    }
    return "$($network -join '.')/$prefix"
}

$normalizedCidr = ConvertTo-AuthorizedPrivateCidr "192.168.50.1/24"

$profile = [ordered]@{
    DESKTOP_AUTO_MONITORING_ENABLED = "true"
    MONITORING_AUTO_REFRESH_ENABLED = "true"
    MONITORING_AUTO_REFRESH_SECONDS = "30"
    LAN_MONITORING_ENABLED = "true"
    LAN_ALLOWED_CIDRS = $normalizedCidr
    LAN_GATEWAY_HINT = "192.168.50.1"
    LAN_DISCOVERY_PING_ENABLED = "true"
    LAN_SERVICE_CHECK_ENABLED = "true"
    LAN_AUTO_DISCOVERY_ON_START = "false"
    LAN_AUTO_SERVICE_CHECK_ON_START = "false"
    LAN_AUTO_DISCOVERY_INTERVAL_SECONDS = "300"
    LAN_AUTO_SERVICE_CHECK_INTERVAL_SECONDS = "600"
    LAN_SERVICE_CHECK_PORTS = "22,80,443,445,3389,8080,8443,3000,5000,5432,6379,8000,9000"
    LAN_SERVICE_CHECK_TIMEOUT_SECONDS = "2"
    LAN_SERVICE_CHECK_MAX_HOSTS = "256"
    LAN_SERVICE_CHECK_MAX_PORTS = "32"
    LAN_REJECT_PUBLIC_CIDRS = "true"
    LAN_SSH_BANNER_DETECTION_ENABLED = "true"
    SERVER_HOST_METRICS_ENABLED = "true"
    SERVER_HOST_METRICS_INTERVAL_SECONDS = "30"
    LAN_ENDPOINT_AGENT_INTERVAL_SECONDS = "30"
}

$repositoryRoot = Resolve-RavenTechRepositoryRoot
$envPath = [IO.Path]::Combine($repositoryRoot, ".env")
if (-not (Test-Path -LiteralPath $envPath -PathType Leaf)) {
    throw "The local .env file does not exist. Copy .env.example to .env, review it locally, and retry."
}

$lines = [Collections.Generic.List[string]]::new()
$lines.AddRange([string[]][IO.File]::ReadAllLines($envPath))
$positions = @{}
for ($index = 0; $index -lt $lines.Count; $index++) {
    if ($lines[$index] -match '^\s*([A-Z][A-Z0-9_]*)\s*=') {
        $key = $Matches[1]
        if ($profile.Contains($key)) {
            if ($positions.ContainsKey($key)) {
                throw "Duplicate active monitoring key detected: $key. Resolve the duplicate manually before retrying."
            }
            $positions[$key] = $index
        }
    }
}

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmssfff")
$backupName = ".env.backup-$timestamp"
$backupPath = [IO.Path]::Combine($repositoryRoot, $backupName)
$temporaryPath = [IO.Path]::Combine($repositoryRoot, ".env.raventech-$timestamp.tmp")
Copy-Item -LiteralPath $envPath -Destination $backupPath -ErrorAction Stop
try {
    foreach ($key in $profile.Keys) {
        $entry = "$key=$($profile[$key])"
        if ($positions.ContainsKey($key)) {
            $lines[$positions[$key]] = $entry
        } else {
            $lines.Add($entry)
        }
    }
    [IO.File]::WriteAllLines($temporaryPath, $lines, [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporaryPath -Destination $envPath -Force -ErrorAction Stop
} catch {
    if (Test-Path -LiteralPath $temporaryPath) {
        Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
    }
    throw "LAN monitoring configuration was not applied. The existing .env remains available and the timestamped backup was preserved."
}

Write-Output "Applied fixed private LAN monitoring profile."
Write-Output "Allowed CIDR: 192.168.50.0/24"
Write-Output "Gateway hint: 192.168.50.1"
Write-Output "Backup: $backupName"
Write-Output "Updated non-secret keys: $($profile.Keys -join ', ')"
Write-Output "Restart required: yes"
Write-Output "Automatic discovery and service checks on startup remain disabled."
