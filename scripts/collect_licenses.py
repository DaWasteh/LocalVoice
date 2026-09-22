"""Copy installed dependency notices into portable distributions."""
from importlib.metadata import distributions
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[1]
out = root / 'licenses' / 'python-packages'
out.mkdir(parents=True, exist_ok=True)
for dist in distributions():
    name = dist.metadata['Name']
    target = out / name
    target.mkdir(exist_ok=True)
    (target / 'package.txt').write_text(f"{name} {dist.version}\nLicense: {dist.metadata.get('License-Expression') or dist.metadata.get('License', '')}\nHome: {dist.metadata.get('Home-page', '')}\n", encoding='utf-8')
    for filename in dist.files or ():
        if any(marker in str(filename).lower() for marker in ('license', 'copying', 'notice')):
            source = Path(dist.locate_file(filename))
            if source.is_file() and source.suffix.lower() in ('', '.txt', '.md', '.rst', '.lgpl', '.gpl'):
                destination = target / Path(*[p for p in filename.parts if p not in ('..', '.')])
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if python_license.exists():
    shutil.copy2(python_license, root / 'licenses' / 'Python-LICENSE.txt')
print('Dependency notices copied to', out)
