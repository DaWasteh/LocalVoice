$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    py -3.14 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.14 (64-bit) installieren und Setup erneut ausführen.' }
}
$Python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
& $Python -c "import sys; assert sys.version_info[:2] == (3,14), 'Bitte .venv mit Python 3.14 neu erstellen'"
if ($LASTEXITCODE -ne 0) { throw 'Falsche Python-Version' }
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip-Update fehlgeschlagen' }
& $Python -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Installation fehlgeschlagen' }
& $Python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Abhängigkeitsprüfung fehlgeschlagen' }
Write-Host 'Bereit. Start: .venv\Scripts\pythonw.exe main.py | EXE: .\Build.ps1'
