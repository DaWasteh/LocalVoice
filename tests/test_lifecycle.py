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


PARENT = """import subprocess, sys, time
sys.path.insert(0, sys.argv[1])
from localvoice.backend import kill_on_close_job, assign_to_job
job = kill_on_close_job()
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
print(child.pid, assign_to_job(job, child), flush=True)
time.sleep(60)
"""


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows job objects')
def test_whisper_process_dies_with_localvoice(tmp_path):
    """A crashed/killed LocalVoice must not leave whisper-server holding RAM/VRAM."""
    import subprocess
    import time
    parent = tmp_path / 'parent.py'
    parent.write_text(PARENT, encoding='utf-8')
    root = str(Path(__file__).resolve().parents[1])
    proc = subprocess.Popen([sys.executable, str(parent), root], stdout=subprocess.PIPE, text=True)
    pid, assigned = proc.stdout.readline().split()
    assert assigned == 'True'
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    child = kernel32.OpenProcess(0x00100000, False, int(pid))  # SYNCHRONIZE
    assert child
    try:
        proc.kill()  # like Task Manager: no cleanup code runs
        proc.wait(timeout=5)
        assert kernel32.WaitForSingleObject(child, 5000) == 0  # WAIT_OBJECT_0: child has exited
    finally:
        kernel32.CloseHandle(child)
