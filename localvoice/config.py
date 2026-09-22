from __future__ import annotations
from dataclasses import dataclass, asdict, fields
import json
import os
from pathlib import Path
import sys


def root_dir() -> Path:
    override = os.environ.get('LOCALVOICE_HOME')
    if override:
        return Path(override).expanduser().resolve()
    return Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]


def assets_dir() -> Path:
    return Path(getattr(sys, '_MEIPASS', root_dir())) / 'assets'


@dataclass
class Settings:
    model: str = 'large-v3'
    device: str = 'vulkan:0' if sys.platform != 'darwin' else 'auto'
    microphone: str = ''
    language: str = 'de'
    theme: str = 'system'
    hotkey: str = 'ctrl+alt+space'
    hotkey_mode: str = 'toggle'
    mode: str = 'final'
    direct: bool = False
    autostart: bool = False
    close_to_tray: bool = True
    chunk_seconds: int = 4
    config_version: int = 2

    @classmethod
    def load(cls, root: Path):
        path = root / 'state/settings.json'
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            defaults = asdict(cls())
            values = {k: v for k, v in data.items() if k in defaults and type(v) is type(defaults[k])}
            obj = cls(**values)
            if values.get('config_version', 1) < 2:
                # v0.1 had an eight-second default. Preserve non-default custom values.
                if values.get('chunk_seconds', 8) == 8:
                    obj.chunk_seconds = 4
                obj.config_version = 2
            for key, options in {'theme': ('dark', 'light', 'system'), 'mode': ('final', 'preview'),
                                 'hotkey_mode': ('toggle', 'hold')}.items():
                if getattr(obj, key) not in options:
                    setattr(obj, key, defaults[key])
            obj.chunk_seconds = max(2, min(20, obj.chunk_seconds))
            return obj
        except (OSError, ValueError, TypeError, AttributeError):
            return cls()

    def save(self, root: Path):
        folder = root / 'state'
        folder.mkdir(parents=True, exist_ok=True)
        temp = folder / 'settings.tmp'
        temp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding='utf-8')
        temp.replace(folder / 'settings.json')
