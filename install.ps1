$ProgressPreference = 'SilentlyContinue'
$d = "$env:TEMP\anti"
New-Item -ItemType Directory -Path $d -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/AdamZoda/ANTI/main/dist/anti-scan.exe" -OutFile "$d\anti-scan.exe" -UseBasicParsing
$f = Get-Item "$d\anti-scan.exe"
if ($f.Length -gt 10MB) {
    & "$d\anti-scan.exe"
} else {
    Write-Host "Download failed - file too small ($($f.Length) bytes)"
}
