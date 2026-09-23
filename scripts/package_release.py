"""Assemble the portable Windows release: dist/LocalVoice-v<version>-windows-x64.zip.

Run after Build.ps1 produced LocalVoice.exe/_internal. Models are downloaded in the
app and never shipped. The Visual C++ runtime needed by whisper-server.exe (MSVC STL,
OpenMP) is copied app-locally from the Visual Studio redistributable folder, so users
do not need to install the VC++ Redistributable.
"""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from localvoice import __version__  # noqa: E402

VC_DLLS = ('msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'vcomp140.dll')
DOCUMENTS = ('README.md', 'LICENSE', 'THIRD_PARTY.md', 'CHANGELOG.md')


def vc_redist_files():
    vswhere = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    if not vswhere.is_file():
        return {}
    install = subprocess.run([str(vswhere), '-latest', '-prerelease', '-products', '*', '-property', 'installationPath'],
                             capture_output=True, text=True).stdout.strip()
    redist = Path(install) / 'VC/Redist/MSVC'
    versions = sorted((p for p in redist.glob('*') if re.fullmatch(r'\d+(\.\d+)+', p.name)),
                      key=lambda p: tuple(map(int, p.name.split('.'))))
    for version in reversed(versions):
        found = {}
        for folder in (version / 'x64').glob('Microsoft.VC*.*'):
            if folder.name.endswith(('.CRT', '.OpenMP')):
                found.update({f.name.lower(): f for f in folder.glob('*.dll') if f.name.lower() in VC_DLLS})
        if len(found) == len(VC_DLLS):
            return found
    return {}


def bundle_vc_runtime():
    runtime = root / 'runtime'
    for name, source in vc_redist_files().items():
        shutil.copy2(source, runtime / name)
    missing = [name for name in VC_DLLS if not (runtime / name).is_file()]
    if missing:
        raise SystemExit(f'Visual C++ runtime DLLs missing in runtime/: {missing}. Install Visual Studio C++ tools.')


def main():
    required = [root / 'LocalVoice.exe', root / '_internal', root / 'runtime/whisper-server.exe',
                root / 'licenses/whisper.cpp-MIT.txt', root / 'licenses/python-packages']
    missing = [str(p.relative_to(root)) for p in required if not p.exists()]
    if missing:
        raise SystemExit(f'Build incomplete, missing: {missing}. Run Build.ps1 and scripts/build_runtime.py first.')
    bundle_vc_runtime()
    dist = root / 'dist'
    dist.mkdir(exist_ok=True)
    archive = dist / f'LocalVoice-v{__version__}-windows-x64.zip'
    archive.unlink(missing_ok=True)
    files = [root / 'LocalVoice.exe', *[root / name for name in DOCUMENTS]]
    for folder in ('_internal', 'runtime', 'licenses'):
        files += sorted(p for p in (root / folder).rglob('*') if p.is_file())
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in files:
            zf.write(path, Path('LocalVoice') / path.relative_to(root))
        zf.writestr('LocalVoice/models/README.txt',
                    'Whisper- und Silero-Modelle werden in LocalVoice unter Einstellungen > Audio & Modelle '
                    'heruntergeladen und hier gespeichert.\n')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (dist / f'{archive.name}.sha256').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    print(f'Release: {archive} ({archive.stat().st_size / 1e6:.0f} MB)\nSHA-256: {digest}')


if __name__ == '__main__':
    main()
