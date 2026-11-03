"""Create a portable source bundle, excluding credentials, caches, and environments."""
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / '.local' / 'lumio-source.tar.gz'
target.parent.mkdir(exist_ok=True)
paths = ['config.py','services.py','bridges.py','server.py','requirements.txt','README.md',
         'web','tests','scripts/test_hosted_voice.py','scripts/test_api_flow.py','scripts/install_linux.sh','scripts/install_service.py','scripts/set_api_keys.py']
with tarfile.open(target, 'w:gz') as archive:
    for relative in paths:
        path = ROOT / relative
        if path.is_dir():
            for child in sorted(path.rglob('*')):
                if child.is_file() and '__pycache__' not in child.parts:
                    archive.add(child, arcname=str(child.relative_to(ROOT)).replace('\\','/'))
        else:
            archive.add(path, arcname=relative)
print(f'Source bundle: {target} ({target.stat().st_size} bytes; no credentials)')
