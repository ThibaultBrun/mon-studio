# Mon Studio - installation Windows (clic droit -> « Exécuter avec PowerShell »)
# Monte tout en local dans le dossier de l'appli : venv + PyQt6, FluidSynth (DLL),
# la banque de sons, ffmpeg, et un raccourci sur le Bureau. Aucune install système requise.
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ROOT
Write-Host "== Mon Studio : installation dans $ROOT ==" -ForegroundColor Cyan

# --- 1. Python ---
$py = $null
foreach ($c in @("py -3","python")) {
  try { & $c.Split()[0] $c.Split()[1] --version *> $null; $py = $c; break } catch {}
}
if (-not $py) { Write-Host "Python 3 introuvable. Installe-le depuis https://www.python.org/downloads/ en cochant « Add Python to PATH », puis relance." -ForegroundColor Red; Read-Host "Entrée pour quitter"; exit 1 }
Write-Host "Python OK ($py)"

# --- 2. venv + PyQt6 ---
& $py.Split() -m venv .venv
$VPY = ".\.venv\Scripts\python.exe"
& $VPY -m pip install --upgrade pip | Out-Null
Write-Host "Installation de PyQt6..." ; & $VPY -m pip install PyQt6 | Out-Null

New-Item -ItemType Directory -Force -Path bin, soundfonts | Out-Null

# --- 3. FluidSynth (DLL) : dernière release win10-x64 depuis GitHub ---
if (-not (Test-Path ".\bin\libfluidsynth-3.dll")) {
  Write-Host "Téléchargement de FluidSynth..."
  $rel = Invoke-RestMethod "https://api.github.com/repos/FluidSynth/fluidsynth/releases/latest" -Headers @{ "User-Agent" = "mon-studio" }
  $asset = $rel.assets | Where-Object { $_.name -match "win10-x64.zip$" -or $_.name -match "win64.zip$" } | Select-Object -First 1
  if (-not $asset) { Write-Host "Release FluidSynth win64 introuvable, installe-la à la main (voir README-Windows.md)." -ForegroundColor Yellow }
  else {
    Invoke-WebRequest $asset.browser_download_url -OutFile fluidsynth.zip -Headers @{ "User-Agent" = "mon-studio" }
    Expand-Archive fluidsynth.zip -DestinationPath _fs -Force
    Get-ChildItem -Recurse _fs -Filter *.dll | ForEach-Object { Copy-Item $_.FullName .\bin\ -Force }
    Remove-Item fluidsynth.zip, _fs -Recurse -Force
    Write-Host "FluidSynth OK"
  }
}

# --- 4. Banque de sons GeneralUser GS ---
if (-not (Test-Path ".\soundfonts\GeneralUser-GS.sf2")) {
  Write-Host "Téléchargement de la banque de sons (~30 Mo)..."
  Invoke-WebRequest "https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2" -OutFile ".\soundfonts\GeneralUser-GS.sf2"
  Write-Host "Banque de sons OK"
}

# --- 5. ffmpeg (export mp3) ---
if (-not (Test-Path ".\bin\ffmpeg.exe")) {
  Write-Host "Téléchargement de ffmpeg..."
  Invoke-WebRequest "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile ffmpeg.zip
  Expand-Archive ffmpeg.zip -DestinationPath _ff -Force
  Get-ChildItem -Recurse _ff -Filter ffmpeg.exe | Select-Object -First 1 | ForEach-Object { Copy-Item $_.FullName .\bin\ffmpeg.exe -Force }
  Remove-Item ffmpeg.zip, _ff -Recurse -Force
  Write-Host "ffmpeg OK"
}

# --- 6. Lanceur + raccourci Bureau ---
$bat = "@echo off`r`ncd /d `"%~dp0`"`r`nstart """" .\.venv\Scripts\pythonw.exe mon_studio.py`r`n"
Set-Content -Path "MonStudio.bat" -Value $bat -Encoding ASCII
$desktop = [Environment]::GetFolderPath("Desktop")
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut("$desktop\Mon Studio.lnk")
$lnk.TargetPath = "$ROOT\MonStudio.bat"
$lnk.WorkingDirectory = $ROOT
$icon = "$ROOT\mon-studio.ico"; if (Test-Path $icon) { $lnk.IconLocation = $icon }
$lnk.Save()

Write-Host "`n== Terminé ! Double-clique sur « Mon Studio » sur le Bureau. ==" -ForegroundColor Green
Read-Host "Entrée pour fermer"
