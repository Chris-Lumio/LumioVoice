"""Enter provider credentials privately on the host running Lumio."""
import argparse
import getpass
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Settings

parser = argparse.ArgumentParser()
parser.add_argument('--groq', action='store_true')
parser.add_argument('--hugging-face', action='store_true')
args = parser.parse_args()
if not (args.groq or args.hugging_face):
    parser.error('Choose --groq or --hugging-face (or both). Credentials are read through hidden prompts.')
settings = Settings()
values = {}
if args.groq:
    values['groq_key'] = getpass.getpass('Groq free-plan API key (hidden, blank retains current): ').strip()
if args.hugging_face:
    values['hf_token'] = getpass.getpass('Hugging Face token (hidden, blank retains current): ').strip()
settings.update(values)
print('Provider settings saved privately. Restart the Lumio service to apply file changes.')
