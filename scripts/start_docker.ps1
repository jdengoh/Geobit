# Set strict error handling
$ErrorActionPreference = "Stop"

Set-StrictMode -Version Latest

if ($PSVersionTable.PSVersion -ge [Version]"7.2") {
    $PSNativeCommandUseErrorActionPreference = $true
}

Write-Host "🚀 Starting backend (Docker)..."

docker compose -f docker-compose.yaml up --build
