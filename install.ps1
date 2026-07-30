$ErrorActionPreference = "Stop"

$installDir = "$env:LOCALAPPDATA\AntiScan"

if (!(Test-Path $installDir)) {
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
}

$exe = "$installDir\anti-scan.exe"

Write-Host "Downloading Anti Scan..."

Invoke-WebRequest `
    -Uri "https://raw.githubusercontent.com/AdamZoda/ANTI/main/dist/anti-scan.exe" `
    -OutFile $exe

Write-Host "Launching..."

Start-Process $exe