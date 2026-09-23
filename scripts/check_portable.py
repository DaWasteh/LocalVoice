"""Run the frozen app from a relocated folder, without a venv or original models path.

With --package the release ZIP itself is extracted and tested, exactly as a user gets it.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--audio', required=True, help='16 kHz mono PCM16 test WAV')
parser.add_argument('--package', help='Release ZIP from scripts/package_release.py')
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='LocalVoice portable test ') as name:
    if args.package:
        with zipfile.ZipFile(args.package) as zf:
            zf.extractall(Path(name) / 'extracted with spaces')
        target = Path(name) / 'extracted with spaces' / 'LocalVoice'
        assert not (target / 'state').exists(), 'Release must not contain private state'
    else:
        target = Path(name) / 'LocalVoice moved'
        target.mkdir()
        shutil.copy2(root / 'LocalVoice.exe', target)
        for folder in ('_internal', 'runtime'):
            shutil.copytree(root / folder, target / folder)
    (target / 'models').mkdir(exist_ok=True)
    for filename in ('ggml-tiny.bin', 'ggml-silero-v6.2.0.bin'):
        shutil.copy2(root / 'models' / filename, target / 'models' / filename)
    shutil.copy2(args.audio, target / 'fixture.wav')
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    for key in ('LOCALVOICE_HOME', 'PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'):
        env.pop(key, None)
    result = subprocess.run([str(target / 'LocalVoice.exe'), '--smoke-test', '--smoke-audio', str(target / 'fixture.wav')],
                            cwd=target, env=env, timeout=120)
    error_log = target / 'state/smoke-error.log'
    assert result.returncode == 0, error_log.read_text(encoding='utf-8') if error_log.exists() else result.returncode
    report = json.loads((target / 'state/smoke-report.json').read_text(encoding='utf-8'))
    assert Path(report['root']) == target
    assert 'country' in report['transcript'].lower()
    assert report['resample_samples'] == 16000
    report['relocation_passed'] = True
    report['tested'] = 'release zip' if args.package else 'relocated build folder'
    # Do not retain an obsolete absolute temporary folder path in the durable report.
    report['root'] = '<temporary relocated directory>'
    (root / 'reports').mkdir(exist_ok=True)
    (root / 'reports/portable.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Portable EXE ({report["tested"]}): relocation, Python 3.14, resampling and real inference passed.')
