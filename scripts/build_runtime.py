"""Rebuild the native runtime from a pinned upstream revision, never from floating main."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

REVISION = '307869af285d7f6f689ba100b3515e2d1b3feb05'
root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--backend', choices=['vulkan', 'metal', 'cpu'], default='metal' if sys.platform == 'darwin' else 'vulkan')
args = parser.parse_args()
source = root / 'build' / 'whisper.cpp'
build = root / 'build' / f'whisper-{args.backend}'
if not source.exists():
    subprocess.run(['git', 'clone', 'https://github.com/ggml-org/whisper.cpp.git', str(source)], check=True)
if subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip():
    raise SystemExit('Runtime source is modified; refusing to discard changes.')
subprocess.run(['git', '-C', str(source), 'checkout', '--detach', REVISION], check=True)
subprocess.run(['cmake', '-S', str(source), '-B', str(build), '-DCMAKE_BUILD_TYPE=Release',
                '-DBUILD_SHARED_LIBS=OFF', '-DWHISPER_BUILD_SERVER=ON',
                f'-DGGML_VULKAN={"ON" if args.backend == "vulkan" else "OFF"}',
                f'-DGGML_METAL={"ON" if args.backend == "metal" else "OFF"}'], check=True)
subprocess.run(['cmake', '--build', str(build), '--config', 'Release', '--target', 'whisper-server', '-j', '4'], check=True)
filename = 'whisper-server.exe' if sys.platform == 'win32' else 'whisper-server'
choices = [build / 'bin' / 'Release' / filename, build / 'bin' / filename]
binary = next((p for p in choices if p.exists()), None)
if binary is None:
    raise SystemExit('Build succeeded but server binary was not found.')
(root / 'runtime').mkdir(exist_ok=True)
shutil.copy2(binary, root / 'runtime' / filename)
(root / 'licenses').mkdir(exist_ok=True)
shutil.copy2(source / 'LICENSE', root / 'licenses' / 'whisper.cpp-MIT.txt')
print('Runtime ready:', root / 'runtime' / filename)
