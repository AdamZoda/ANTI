# ANTI Defense System - Silent Loader & Pre-Clean Self-Destruct
# Usage: powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/AdamZoda/ANTI/main/install.ps1 | iex"

$ErrorActionPreference = "SilentlyContinue"

# 0. Nettoyage immédiat de l'ancien environnement
Remove-Item -Path "$env:LOCALAPPDATA\AntiScan" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$env:TEMP\AntiScan*"        -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$env:TEMP\ANTI.exe"         -Recurse -Force -ErrorAction SilentlyContinue
Clear-Host

$REPO_URL   = "https://raw.githubusercontent.com/AdamZoda/ANTI/main"
$installDir = "$env:LOCALAPPDATA\AntiScan"
$exePath    = "$installDir\anti-scan.exe"

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$CLEANUP_TARGETS = @(
    "$env:TEMP\anti-scan.exe",
    "$env:TEMP\AntiScan*",
    "$env:LOCALAPPDATA\AntiScan*",
    "$env:APPDATA\AntiScan*",
    "$env:USERPROFILE\Downloads\anti-scan*.exe"
)

# 1. Téléchargement silencieux du nouvel exécutable anti-scan.exe
$ts = [DateTimeOffset]::Now.ToUnixTimeSeconds()
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri "$REPO_URL/dist/anti-scan.exe?t=$ts" -OutFile $exePath -UseBasicParsing -Headers @{"Cache-Control"="no-cache"}
} catch {
    Write-Host "[X] Impossible de démarrer le scanner." -ForegroundColor Red
    exit 1
}

# 2. Vérifier que le fichier est bien téléchargé et non vide
if (-not (Test-Path $exePath) -or (Get-Item $exePath).Length -lt 100000) {
    Write-Host "[X] Fichier corrompu ou téléchargement incomplet." -ForegroundColor Red
    exit 1
}

# Assure que la console reste 100% propre avant l'ASCII Art
Clear-Host

# 3. Lancement direct du scanner
try {
    $proc = Start-Process -FilePath $exePath -Wait -PassThru -NoNewWindow
} catch {}

# 4. Auto-destruction silencieuse post-scan
Start-Sleep -Milliseconds 500
foreach ($target in $CLEANUP_TARGETS) {
    try {
        Get-ChildItem -Path $target -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    } catch {}
}

# Tâche de nettoyage différé pour supprimer complètement le dossier
$selfDestructCmd = "cmd.exe /c timeout /t 2 /nobreak >nul & rmdir /s /q `"$installDir`" 2>nul"
Start-Process -FilePath "cmd.exe" -ArgumentList "/c $selfDestructCmd" -WindowStyle Hidden