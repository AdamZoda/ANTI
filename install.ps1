# ANTI Defense System - Installation Script
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"

$REPO_URL = "https://raw.githubusercontent.com/AdamZoda/ANTI/main"
$installDir = "$env:LOCALAPPDATA\AntiScan"
$exePath    = "$installDir\anti-scan.exe"
$verPath    = "$installDir\version.txt"

# --- Couleurs ---
function Write-OK   { param($msg) Write-Host "[OK] $msg"  -ForegroundColor Green }
function Write-INFO { param($msg) Write-Host "[..] $msg"  -ForegroundColor Cyan  }
function Write-WARN { param($msg) Write-Host "[!]  $msg"  -ForegroundColor Yellow }
function Write-ERR  { param($msg) Write-Host "[X]  $msg"  -ForegroundColor Red   }

Write-Host ""
Write-Host "================================================" -ForegroundColor DarkBlue
Write-Host "   ANTI DEFENSE SYSTEM - Installer"              -ForegroundColor White
Write-Host "================================================" -ForegroundColor DarkBlue
Write-Host ""

# --- Vérification de la version locale ---
$localVersion = "0.0"
if (Test-Path $verPath) {
    $localVersion = (Get-Content $verPath -Raw).Trim()
}

# --- Récupération de la version distante ---
try {
    Write-INFO "Vérification de la dernière version disponible..."
    $remoteVersion = (Invoke-RestMethod -Uri "$REPO_URL/version.json").version
    Write-INFO "Version locale   : v$localVersion"
    Write-INFO "Version distante : v$remoteVersion"
} catch {
    Write-WARN "Impossible de vérifier la version en ligne. Installation forcée..."
    $remoteVersion = "0.0"
}

# --- Téléchargement si nécessaire ---
if ((-not (Test-Path $exePath)) -or ($remoteVersion -ne $localVersion)) {

    # Créer le dossier si absent
    if (!(Test-Path $installDir)) {
        New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    }

    Write-INFO "Téléchargement de anti-scan.exe (v$remoteVersion)..."

    try {
        # Désactiver la vérification de progression pour accélérer le téléchargement
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri "$REPO_URL/dist/anti-scan.exe" -OutFile $exePath -UseBasicParsing

        # Enregistrer la version installée
        $remoteVersion | Out-File -FilePath $verPath -Encoding UTF8 -NoNewline

        Write-OK "Installation réussie - v$remoteVersion"
    } catch {
        Write-ERR "Échec du téléchargement : $_"
        exit 1
    }

} else {
    Write-OK "Déjà à jour - v$localVersion"
}

# --- Lancement du scan ---
Write-Host ""
Write-INFO "Démarrage du scan..."
Write-Host ""

try {
    Start-Process -FilePath $exePath -Wait -NoNewWindow
} catch {
    Write-ERR "Erreur au lancement : $_"
    exit 1
}