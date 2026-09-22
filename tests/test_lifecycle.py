import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from localvoice.integration import set_autostart


def test_windows_autostart_quotes_paths_and_uses_tray(monkeypatch, tmp_path):
    import localvoice.integration as integration
    monkeypatch.setattr(integration, 'IS_WINDOWS', True)
    calls = []
    class Key:
        def __enter__(self): return self
        def __exit__(self, *args): pass
    fake = SimpleNamespace(HKEY_CURRENT_USER=1, REG_SZ=1, CreateKey=lambda *_: Key(),
        SetValueEx=lambda *args: calls.append(args), DeleteValue=lambda *args: calls.append(args))
    monkeypatch.setitem(sys.modules, 'winreg', fake)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'With spaces' / 'LocalVoice.exe'))
    set_autostart(True, tmp_path)
    assert calls[0][-1].startswith('"') and calls[0][-1].endswith(' --tray')
    assert calls[0][1] == 'LocalVoice'
    set_autostart(False, tmp_path)
    assert calls[-1][1] == 'LocalVoice'
