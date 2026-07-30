# ANTI Defense System - Installation Script
# Usage: powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/AdamZoda/ANTI/main/install.ps1 | iex"

$ErrorActionPreference = "Stop"

$REPO_URL   = "https://raw.githubusercontent.com/AdamZoda/ANTI/main"
$installDir = "$env:LOCALAPPDATA\AntiScan"
$exePath    = "$installDir\anti-scan.exe"
$verPath    = "$installDir\version.txt"

# Anciens emplacements possibles (nettoyage des versions précédentes)
$LEGACY_PATHS = @(
    "$env:TEMP\anti-scan.exe",
    "$env:TEMP\AntiScan",
    "$env:LOCALAPPDATA\AntiScan",
    "$env:APPDATA\AntiScan",
    "$env:USERPROFILE\Downloads\anti-scan.exe"
)

# --- Couleurs ---
function Write-OK   { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green  }
function Write-INFO { param($msg) Write-Host "[..] $msg" -ForegroundColor Cyan   }
function Write-WARN { param($msg) Write-Host "[!]  $msg" -ForegroundColor Yellow }
function Write-ERR  { param($msg) Write-Host "[X]  $msg" -ForegroundColor Red    }

Write-Host ""
Write-Host "================================================" -ForegroundColor DarkBlue
Write-Host "   ANTI DEFENSE SYSTEM - Installer"              -ForegroundColor White
Write-Host "================================================" -ForegroundColor DarkBlue
Write-Host ""

# --- Nettoyage des anciennes versions ---
Write-INFO "Nettoyage des anciennes versions..."
foreach ($path in $LEGACY_PATHS) {
    if (Test-Path $path) {
        try {
            Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
        } catch {}
    }
}
Write-OK "Anciennes versions supprimées."

# --- Récupération de la version distante ---
$remoteVersion = "0.0"
try {
    Write-INFO "Vérification de la dernière version disponible..."
    $remoteVersion = (Invoke-RestMethod -Uri "$REPO_URL/version.json" -UseBasicParsing).version
    Write-INFO "Version distante : v$remoteVersion"
} catch {
    Write-WARN "Impossible de vérifier la version. Téléchargement forcé..."
}

# --- Création du dossier propre ---
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

# --- Téléchargement de l'exe ---
Write-INFO "Téléchargement de anti-scan.exe (v$remoteVersion)..."
try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri "$REPO_URL/dist/anti-scan.exe" -OutFile $exePath -UseBasicParsing
    $remoteVersion | Out-File -FilePath $verPath -Encoding UTF8 -NoNewline
    Write-OK "Téléchargement réussi - v$remoteVersion"
} catch {
    Write-ERR "Échec du téléchargement : $_"
    exit 1
}

# --- Lancement du scan ---
Write-Host ""
Write-INFO "Démarrage du scan..."
Write-Host ""

try {
    Start-Process -FilePath $exePath -Wait -NoNewWindow
} catch {
    Write-ERR "Erreur au lancement : $_"
}

# --- Nettoyage automatique complet ---
Write-Host ""
Write-INFO "Nettoyage automatique en cours..."
try {
    if (Test-Path $installDir) {
        Remove-Item -Path $installDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-OK "Nettoyage terminé. Aucune trace laissée sur le PC."
} catch {}