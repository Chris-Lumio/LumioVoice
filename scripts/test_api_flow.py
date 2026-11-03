"""Live checks with a generated Arabic recording; not a live microphone test."""
import asyncio
import json
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import aiohttp
from config import Settings, PRIVATE
from services import Services

async def main():
    settings = Settings()
    if not settings.data['groq_key']:
        raise SystemExit('A Groq free-plan key must be configured first.')
    sample = PRIVATE / 'voice-test.wav'
    if not sample.exists():
        raise SystemExit('Generate the Arabic sample with scripts/test_hosted_voice.py first.')
    result = {'input': 'previously generated Arabic WAV; no live microphone used'}
    async with aiohttp.ClientSession() as session:
        services = Services(settings, session)
        models = await services.models()
        result['chat_model_available'] = settings.data['chat_model'] in models
        result['speech_model_available'] = settings.data['stt_model'] in models
        if not result['chat_model_available'] or not result['speech_model_available']:
            available = [m for m in models if any(x in m for x in ('qwen', 'llama', 'whisper'))]
            raise SystemExit('A configured model is not available on this account. Relevant models: ' + ', '.join(available))
        start = time.monotonic()
        result['transcript'] = await services.transcribe(sample.read_bytes())
        result['recognition_seconds'] = round(time.monotonic() - start, 2)
        start = time.monotonic()
        answer = await services.chat([{'role': 'user', 'content': result['transcript']}])
        result['reply'] = answer['content']
        result['reply_seconds'] = round(time.monotonic() - start, 2)
        if not result['transcript'] or not result['reply']:
            raise SystemExit('Recognition or AI reply was empty.')
        result['passed'] = True
    (PRIVATE / 'api-flow-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

asyncio.run(main())
