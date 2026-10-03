"""Write the Windows version resource for LocalVoice.exe (PyInstaller --version-file).

An EXE without publisher/version metadata looks anonymous to antivirus heuristics.
"""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from localvoice import __version__  # noqa: E402

numbers = tuple(int(part) for part in __version__.split('.')[:4] if part.isdigit())
numbers += (0,) * (4 - len(numbers))
strings = {
    'CompanyName': 'LocalVoice contributors',
    'FileDescription': 'LocalVoice - private offline dictation',
    'FileVersion': __version__,
    'InternalName': 'LocalVoice',
    'LegalCopyright': 'Copyright (c) 2026 LocalVoice contributors. MIT License.',
    'OriginalFilename': 'LocalVoice.exe',
    'ProductName': 'LocalVoice',
    'ProductVersion': __version__,
}
entries = ', '.join(f'StringStruct({key!r}, {value!r})' for key, value in strings.items())
out = root / 'build' / 'version_info.txt'
out.parent.mkdir(exist_ok=True)
out.write_text(
    f'VSVersionInfo(ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f, flags=0x0, '
    f'OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)), '
    f"kids=[StringFileInfo([StringTable('040904B0', [{entries}])]), "
    f"VarFileInfo([VarStruct('Translation', [1033, 1200])])])\n", encoding='utf-8')
print('Version resource written to', out)
