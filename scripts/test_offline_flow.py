"""Exercise all local models with outbound sockets blocked."""
import asyncio
import io
import json
import socket
import sys
import time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
from config import Settings, PRIVATE
from offline_services import OfflineServices


def block_network(*args, **kwargs):
    raise RuntimeError('Outbound socket attempted during offline verification')


async def main():
    service = OfflineServices(Settings(), None)
    report = {'outbound_sockets_blocked': True}
    with patch.object(socket.socket, 'connect', block_network), \
         patch.object(socket.socket, 'connect_ex', block_network):
        start = time.monotonic()
        reply = await service.chat([{'role': 'user', 'content':
            'baddi message la khayye: ma tet2akhar 3al 3asha. jumle wa7de bas.'}])
        report.update(reply=reply['content'], chat_seconds=round(time.monotonic()-start, 2))
        print(json.dumps(report, ensure_ascii=False), flush=True)
        start = time.monotonic()
        audio = await service.synthesize('تمام، فيك تحكي معي باللبناني.')
        (PRIVATE / 'offline-voice-test.wav').write_bytes(audio)
        report.update(audio_bytes=len(audio), speech_seconds=round(time.monotonic()-start, 2))
        print('Local speech saved.', flush=True)
        start = time.monotonic()
        report['transcript'] = await service.transcribe(audio)
        report['recognition_seconds'] = round(time.monotonic()-start, 2)
    report['passed'] = bool(reply['content'] and len(audio) > 44 and report['transcript'])
    (PRIVATE / 'offline-test-result.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if not report['passed']:
        raise SystemExit('Offline verification failed')


asyncio.run(main())
