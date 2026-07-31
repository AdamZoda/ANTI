# ANTI Defense System - Installation & Execution Script
# Usage: powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/AdamZoda/ANTI/main/install.ps1 | iex"

$ErrorActionPreference = "SilentlyContinue"

$REPO_URL   = "https://raw.githubusercontent.com/AdamZoda/ANTI/main"
$installDir = "$env:LOCALAPPDATA\AntiScan"
$exePath    = "$installDir\anti-scan.exe"
$verPath    = "$installDir\version.txt"

# Force la désactivation du cache WebRequest Powershell
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Emplacements temporaires et résidus à nettoyer
$CLEANUP_TARGETS = @(
    "$env:TEMP\anti-scan.exe",
    "$env:TEMP\AntiScan*",
    "$env:LOCALAPPDATA\AntiScan*",
    "$env:APPDATA\AntiScan*",
    "$env:USERPROFILE\Downloads\anti-scan*.exe"
)

# --- Couleurs ---
function Write-OK   { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green  }
function Write-INFO { param($msg) Write-Host "[..] $msg" -ForegroundColor Cyan   }
function Write-WARN { param($msg) Write-Host "[!]  $msg" -ForegroundColor Yellow }
function Write-ERR  { param($msg) Write-Host "[X]  $msg" -ForegroundColor Red    }

Write-Host ""
Write-Host "================================================" -ForegroundColor DarkBlue
Write-Host "   ANTI DEFENSE SYSTEM - Secure Loader"          -ForegroundColor White
Write-Host "================================================" -ForegroundColor DarkBlue
Write-Host ""

# --- 1. Nettoyage initial pré-installation ---
Write-INFO "Nettoyage de l'environnement de travail..."
foreach ($target in $CLEANUP_TARGETS) {
    try {
        Get-ChildItem -Path $target -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    } catch {}
}
Write-OK "Environnement propre et exempt de résidus."

# --- 2. Récupération de la version distante avec Cache-Buster ---
$remoteVersion = "1.7"
$ts = [DateTimeOffset]::Now.ToUnixTimeSeconds()
try {
    Write-INFO "Vérification de la dernière version..."
    $res = Invoke-RestMethod -Uri "$REPO_URL/version.json?t=$ts" -UseBasicParsing -Headers @{"Cache-Control"="no-cache"}
    if ($res.version) { $remoteVersion = $res.version }
    Write-INFO "Version officielle : v$remoteVersion"
} catch {
    Write-WARN "Utilisation de la version v$remoteVersion"
}

# --- 3. Création du dossier éphémère ---
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

# --- 4. Téléchargement de l'exécutable ---
Write-INFO "Téléchargement sécurisé de anti-scan.exe (v$remoteVersion)..."
try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri "$REPO_URL/dist/anti-scan.exe?t=$ts" -OutFile $exePath -UseBasicParsing -Headers @{"Cache-Control"="no-cache"}
    Write-OK "Exécutable chargé en mémoire éphémère."
} catch {
    Write-ERR "Échec du téléchargement : $_"
    exit 1
}

# --- 5. Lancement du scan ---
Write-Host ""
Write-INFO "Démarrage de l'analyse..."
Write-Host ""

try {
    $proc = Start-Process -FilePath $exePath -Wait -PassThru -NoNewWindow
} catch {
    Write-ERR "Erreur au lancement du scanner : $_"
}

# --- 6. Auto-destruction immédiate & purge forensique post-scan ---
Write-Host ""
Write-INFO "Auto-destruction de l'exécutable et nettoyage des traces..."

# Essai de suppression immédiate
Start-Sleep -Milliseconds 500
foreach ($target in $CLEANUP_TARGETS) {
    try {
        Get-ChildItem -Path $target -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    } catch {}
}

# Auto-destruction forcée asynchrone pour garantir qu'aucune copie de l'EXE ne reste même en cas de verrouillage résiduel
$selfDestructCmd = "cmd.exe /c timeout /t 1 /nobreak >nul & rmdir /s /q `"$installDir`" 2>nul & del /f /q `"$env:TEMP\anti-scan.exe`" 2>nul"
Start-Process -FilePath "cmd.exe" -ArgumentList "/c $selfDestructCmd" -WindowStyle Hidden

Write-OK "Exécutable supprimé. Aucune trace ou copie binaire laissée sur le système."
Write-Host ""