"""Native login entries, without modifying the test user's real autostart."""
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest
from localvoice import integration


@pytest.fixture
def sandbox(monkeypatch, tmp_path):
    monkeypatch.setattr(integration, 'IS_WINDOWS', False)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path / 'home'))
    monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
    return tmp_path


@pytest.mark.parametrize('platform', ['linux', 'darwin'])
@pytest.mark.parametrize('frozen', [False, True])
def test_login_entry_enable_update_disable(sandbox, monkeypatch, platform, frozen):
    root = sandbox / 'Local Voice ä & %f'
    executable = str(sandbox / 'venv with spaces' / 'python')
    monkeypatch.setattr(integration, 'sys', SimpleNamespace(platform=platform, executable=executable, frozen=frozen))
    entry = (Path.home() / ('Library/LaunchAgents/com.localvoice.LocalVoice.plist' if platform == 'darwin'
                            else '.config/autostart/LocalVoice.desktop'))
    integration.set_autostart(False, root)
    assert not entry.parent.exists()
    integration.set_autostart(True, root)
    first = entry.read_bytes()
    if platform == 'darwin':
        data = plistlib.loads(first)
        assert data == {'Label': 'com.localvoice.LocalVoice', 'RunAtLoad': True,
                        'ProgramArguments': [executable] + ([] if frozen else [str(root / 'main.py')]) + ['--tray'],
                        'WorkingDirectory': str(root)}
        if sys.platform == 'darwin':
            subprocess.run(['plutil', '-lint', str(entry)], check=True)
    else:
        text = first.decode()
        assert '[Desktop Entry]\nType=Application\n' in text
        assert 'Exec=/usr/bin/env -- "' in text
        assert text.count('--tray') == 1 and 'Terminal=false' in text
        assert ('main.py' in text) is not frozen
        if not frozen:
            assert '%%f' in text
    integration.set_autostart(True, root)
    assert entry.read_bytes() == first
    integration.set_autostart(True, sandbox / 'moved')
    assert entry.read_bytes() != first
    integration.set_autostart(False, root)
    integration.set_autostart(False, root)
    assert not entry.exists() and not list(entry.parent.iterdir())


@pytest.mark.parametrize('config', ['', 'relative/config', 'absolute'])
def test_linux_config_home(sandbox, monkeypatch, config):
    value = str(sandbox / 'custom config') if config == 'absolute' else config
    monkeypatch.setenv('XDG_CONFIG_HOME', value)
    monkeypatch.setattr(integration, 'sys', SimpleNamespace(platform='linux', executable=sys.executable))
    integration.set_autostart(True, sandbox)
    folder = Path(value) if config == 'absolute' else Path.home() / '.config'
    assert (folder / 'autostart/LocalVoice.desktop').is_file()


@pytest.mark.parametrize('platform', ['linux', 'darwin'])
def test_failed_replace_preserves_entry(sandbox, monkeypatch, platform):
    monkeypatch.setattr(integration, 'sys', SimpleNamespace(platform=platform, executable=sys.executable))
    integration.set_autostart(True, sandbox)
    entry = next(p for p in Path.home().rglob('*') if p.is_file())
    before = entry.read_bytes()
    def fail(*args, **kwargs):
        raise PermissionError('read only')
    monkeypatch.setattr(Path, 'replace', fail)
    with pytest.raises(PermissionError):
        integration.set_autostart(True, sandbox / 'moved')
    assert entry.read_bytes() == before
    assert list(entry.parent.iterdir()) == [entry]
    monkeypatch.setattr(Path, 'unlink', fail)
    with pytest.raises(PermissionError):
        integration.set_autostart(False, sandbox)


def test_unsupported_platform_is_explicit(sandbox, monkeypatch):
    monkeypatch.setattr(integration, 'sys', SimpleNamespace(platform='unsupported'))
    with pytest.raises(RuntimeError, match='Windows, Linux und macOS'):
        integration.set_autostart(True, sandbox)


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='Native Linux desktop parser')
@pytest.mark.parametrize('frozen', [False, True])
def test_linux_desktop_launch_preserves_arguments(sandbox, monkeypatch, frozen):
    """Run the actual Exec via GLib, not a home-grown parser that could share a bug."""
    python = '/usr/bin/python3'
    probe = subprocess.run([python, '-c', 'from gi.repository import Gio'], capture_output=True)
    if probe.returncode:
        pytest.skip('python3-gi required for native desktop launch check')
    root = sandbox / 'Local Voice ä %f $HOME `echo nope` " \\ tab\tline\nend'
    root.mkdir()
    result = sandbox / 'result.json'
    script = ('import json, os, pathlib, sys\n'
              f'pathlib.Path({str(result)!r}).write_text(json.dumps([sys.argv, os.getcwd()]))\n')
    if frozen:
        executable = root / 'LocalVoice'
        executable.write_text(f'#!{sys.executable}\n' + script)
        executable.chmod(0o700)
    else:
        executable = sandbox / 'venv python'
        executable.symlink_to(sys.executable)
        (root / 'main.py').write_text(script)
    monkeypatch.setattr(integration, 'sys', SimpleNamespace(platform='linux', executable=str(executable), frozen=frozen))
    integration.set_autostart(True, root)
    entry = Path.home() / '.config/autostart/LocalVoice.desktop'
    if shutil.which('desktop-file-validate'):
        subprocess.run(['desktop-file-validate', str(entry)], check=True)
    subprocess.run([python, '-c', 'from gi.repository import Gio; import sys; '
                    'app = Gio.DesktopAppInfo.new_from_filename(sys.argv[1]); '
                    'assert app is not None; assert app.launch([], None)', str(entry)], check=True)
    deadline = time.monotonic() + 5
    while not result.exists() and time.monotonic() < deadline:
        time.sleep(.02)
    argv, cwd = json.loads(result.read_text())
    assert argv == [str(executable if frozen else root / 'main.py'), '--tray']
    assert cwd == str(root)
    if not frozen:
        assert str(executable) in entry.read_text()  # venv symlink must not be resolved
