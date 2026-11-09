$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m pip install "flet[all]" flet-camera flet-charts
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
# Invoke the installed CLI entry point without relying on Windows PATH shortcuts.
python -c "from importlib.metadata import entry_points; import sys; sys.argv=['flet','build','apk']; next(e for e in entry_points(group='console_scripts') if e.name=='flet').load()()"
if ($LASTEXITCODE -ne 0) { throw "APK build failed. Keep the error output for troubleshooting." }
Write-Host "Build completed. Look in build\apk for the APK."
