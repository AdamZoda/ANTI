$d = "$env:TEMP\anti"
New-Item -ItemType Directory -Path $d -Force | Out-Null
& curl.exe -L -o "$d\anti-scan.exe" "https://github.com/AdamZoda/ANTI/raw/main/dist/anti-scan.exe" --progress-bar
$f = Get-Item "$d\anti-scan.exe"
if ($f.Length -gt 10MB) {
    & "$d\anti-scan.exe"
} else {
    Write-Host "Download failed: $($f.Length) bytes"
}
