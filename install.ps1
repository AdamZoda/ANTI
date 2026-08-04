$d = "$env:TEMP\anti"
New-Item -ItemType Directory -Path $d -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/AdamZoda/ANTI/main/dist/anti-scan.exe" -OutFile "$d\anti-scan.exe"
& "$d\anti-scan.exe"
