#!/usr/bin/env bash
# Run from an extracted Lumio source directory. Does not require sudo or install models.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10 or later is required"'
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
printf '\nInstalled. Run .venv/bin/python server.py to start the localhost test desk.\n'
printf 'For Home Assistant on a separate machine/container, see README.md before using --lan.\n'
