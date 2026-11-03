"""One-time online preparation; runtime uses local files only."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from huggingface_hub import snapshot_download
from config import PRIVATE

models = PRIVATE / 'models'
for repo, folder in [('Qwen/Qwen3-1.7B', 'chat'),
                     ('Systran/faster-whisper-small', 'whisper'),
                     ('k2-fsa/OmniVoice', 'voice')]:
    print(f'Downloading {repo}', flush=True)
    snapshot_download(repo, local_dir=models / folder,
                      allow_patterns=['*.json', '*.safetensors', '*.txt', '*.model',
                                      '*.bin', '*.tiktoken', '*.jinja', 'audio_tokenizer/*'],
                      ignore_patterns=['pytorch_model.bin', 'training*', 'optimizer*'],
                      max_workers=3)
if not (models / 'voice' / 'audio_tokenizer' / 'config.json').exists():
    snapshot_download('eustlb/higgs-audio-v2-tokenizer',
                      local_dir=models / 'voice' / 'audio_tokenizer',
                      allow_patterns=['*.json', '*.safetensors', '*.txt'], max_workers=3)
print('Offline model files ready.', flush=True)
