"""Opt-in real inference check: --audio path/to/16k-mono.wav --device cpu."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import wave
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from localvoice.backend import Whisper
from localvoice.config import Settings, root_dir

parser = argparse.ArgumentParser()
parser.add_argument('--audio', required=True)
parser.add_argument('--model', default='tiny')
parser.add_argument('--device', default='cpu')
args = parser.parse_args()
with wave.open(args.audio) as wav:
    assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)
    speech = np.frombuffer(wav.readframes(wav.getnframes()), '<i2').astype(np.float32) / 32768
settings = Settings(model=args.model, device=args.device, language='en')
engine = Whisper(root_dir())
report = {'model': args.model, 'device': args.device}
try:
    start = time.monotonic()
    report['silence'] = engine.transcribe(np.zeros(16000, np.float32), settings)
    assert report['silence'] == '' and engine.proc is None
    report['speech'] = engine.transcribe(speech, settings)
    report['speech_seconds'] = round(time.monotonic() - start, 2)
    assert 'country' in report['speech'].lower(), report
    noise = np.random.default_rng(42).normal(0, .004, 16000 * 4).astype(np.float32)
    report['noise'] = engine.transcribe(noise, settings)
    assert report['noise'] == '', report
    report['passed'] = True
finally:
    engine.close()
    report['process_stopped'] = engine.proc is None
    folder = root_dir() / 'reports'
    folder.mkdir(exist_ok=True)
    (folder / f'backend-{args.model}-{args.device.replace(":", "-")}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
