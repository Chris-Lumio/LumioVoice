"""Install this checkout as a dedicated systemd user service (Linux only)."""
import os
import subprocess
import sys
import json
import time
import urllib.request
from pathlib import Path

if os.name == 'nt':
    raise SystemExit('This helper is for the Raspberry Pi / Linux host.')
root = Path(__file__).resolve().parents[1]
unit_path = Path.home() / '.config/systemd/user/lumio-voice-api.service'
unit = f'''[Unit]
Description=Lumio Lebanese Arabic API voice bridge
After=network-online.target

[Service]
Type=simple
WorkingDirectory={root}
ExecStart={root}/.venv/bin/python {root}/server.py --desk-port 8791
Restart=on-failure
RestartSec=5
TimeoutStopSec=20
UMask=0077
NoNewPrivileges=true

[Install]
WantedBy=default.target
'''
unit_path.parent.mkdir(parents=True, exist_ok=True)
if unit_path.exists():
    old_unit = unit_path.read_text()
    if f'WorkingDirectory={root}\n' not in old_unit or 'Description=Lumio Lebanese Arabic API voice bridge\n' not in old_unit:
        raise SystemExit(f'A different service already exists at {unit_path}; leaving it unchanged.')
unit_path.write_text(unit)
subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
subprocess.run(['systemctl', '--user', 'enable', '--now', 'lumio-voice-api.service'], check=True)
subprocess.run(['systemctl', '--user', 'is-active', 'lumio-voice-api.service'], check=True)
for attempt in range(20):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8791/api/status', timeout=1) as response:
            status = json.load(response)
        if status.get('tts_language') == 'Levantine Arabic':
            break
    except (OSError, ValueError):
        pass
    time.sleep(0.5)
else:
    raise SystemExit('Service did not pass its HTTP readiness check; inspect its user journal.')
print('LUMIO_SERVICE_READY')
