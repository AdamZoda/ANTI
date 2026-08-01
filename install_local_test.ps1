$ErrorActionPreference = "SilentlyContinue"
$installDir = "$env:LOCALAPPDATA\AntiScan"
$exePath    = "$installDir\anti-scan.exe"

try {
    Get-Process -Name "anti-scan" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
} catch {}
Start-Sleep -Milliseconds 500

try {
    if (Test-Path $installDir) {
        Remove-Item -Path $exePath -Force -ErrorAction SilentlyContinue
    } else {
        $null = New-Item -ItemType Directory -Force -Path $installDir
    }
} catch {}

# Copier l'exécutable local
Copy-Item -Path "c:/Users/adamm/Documents/ANTI/dist/anti-scan.exe" -Destination $exePath -Force

# Lancement asynchrone avec privileges Administrateur
try {
    Start-Process -FilePath $exePath -Verb RunAs -WindowStyle Hidden
} catch {
    try {
        Start-Process -FilePath $exePath -WindowStyle Hidden
    } catch {}
}

exit 0
