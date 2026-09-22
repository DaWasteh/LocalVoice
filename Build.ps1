$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$Python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
& $Python -c "import sys; assert sys.version_info[:2] == (3,14), 'Build requires Python 3.14'"
if ($LASTEXITCODE -ne 0) { throw 'Run Setup.ps1 with Python 3.14 first.' }
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped.' }
& $Python scripts/collect_licenses.py
if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
& $Python -m PyInstaller --noconfirm --clean --onedir --windowed --name LocalVoice --icon "$PSScriptRoot/assets/localvoice.ico" --add-data "$PSScriptRoot/assets;assets" --collect-data _sounddevice_data --distpath build/package --workpath build/pyinstaller --specpath build main.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
Copy-Item build/package/LocalVoice/LocalVoice.exe . -Force
if (Test-Path '_internal') { Remove-Item '_internal' -Recurse -Force }
Copy-Item build/package/LocalVoice/_internal . -Recurse -Force
& $Python -c "import sys,json,pathlib; pathlib.Path('build-info.json').write_text(json.dumps({'python':sys.version,'platform':sys.platform},indent=2),encoding='utf-8')"
Write-Host 'Ready: LocalVoice.exe. Keep _internal/, runtime/, models/ and licenses/ beside it.'
