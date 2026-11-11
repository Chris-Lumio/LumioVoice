"""Run the local test desk and native Home Assistant protocol bridges."""
import argparse
import asyncio
import contextlib
import io
import json
import wave
import time
from datetime import datetime, timezone
from pathlib import Path
from aiohttp import web, ClientSession
from wyoming.server import AsyncServer
from config import Settings, ROOT, PRIVATE
from services import Services
from bridges import VoiceHandler, ollama_app

METRICS_FILE = PRIVATE / 'performance.jsonl'
def record_metric(kind, started, ok, error=None, **details):
    METRICS_FILE.parent.mkdir(exist_ok=True)
    entry = {'timestamp': datetime.now(timezone.utc).isoformat(), 'kind': kind,
             'duration_ms': round((time.perf_counter()-started)*1000, 1), 'ok': bool(ok), **details}
    if error: entry['error'] = str(error)[:500]
    with METRICS_FILE.open('a', encoding='utf-8') as f: f.write(json.dumps(entry, ensure_ascii=False)+'\n')
def read_metrics():
    if not METRICS_FILE.exists(): return []
    rows=[]
    for line in METRICS_FILE.read_text(encoding='utf-8').splitlines()[-500:]:
        try: rows.append(json.loads(line))
        except json.JSONDecodeError: pass
    return list(reversed(rows))

@web.middleware
async def local_only(request, handler):
    # The settings desk always stays on loopback, even when voice bridges use LAN.
    if request.host.split(':')[0] not in ('127.0.0.1', 'localhost'):
        raise web.HTTPForbidden(text='Open this desk through localhost.')
    origin = request.headers.get('Origin')
    if origin and origin not in ('http://' + request.host,):
        raise web.HTTPForbidden(text='Cross-origin requests are not allowed.')
    try:
        response = await handler(request)
    except web.HTTPException:
        raise
    except Exception as error:
        response = web.json_response({'error': str(error)}, status=400)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
    return response

def desk_app(settings, services, lan=False):
    app = web.Application(middlewares=[local_only], client_max_size=10*1024*1024)
    async def index(request):
        return web.FileResponse(ROOT / 'web' / 'index.html')
    async def asset(request):
        name = request.match_info['name']
        if name not in ('app.js', 'style.css', 'performance.js'):
            raise web.HTTPNotFound()
        return web.FileResponse(ROOT / 'web' / name)
    async def status(request):
        return web.json_response({**settings.public(), **({'chat_model': 'local-qwen3-1.7b',
            'stt_model': 'local-whisper-small'} if getattr(services, 'offline', False) else {}), 'lan_enabled': lan,
            'offline': bool(getattr(services, 'offline', False)),
            'wyoming_port': 10700, 'ollama_port': 11435, 'accent_target': 'Lebanese Arabic',
            'accent_note': 'Levantine Arabic is selected. A Lebanese reference recording improves consistency; accent is not guaranteed.'})
    async def performance(request): return web.FileResponse(ROOT / 'web' / 'performance.html')
    async def metrics(request): return web.json_response({'items': read_metrics()})
    async def clear_metrics(request): METRICS_FILE.unlink(missing_ok=True); return web.json_response({'items': []})
    async def configure(request):
        values = await request.json()
        settings.update(values)
        return await status(request)
    async def chat(request):
        started=time.perf_counter()
        body = await request.json()
        try:
            result=await services.chat(body.get('messages')); record_metric('chat',started,True,model=settings.data.get('chat_model'),input_messages=len(body.get('messages') or []),output_characters=len(result.get('content') or '')); return web.json_response(result)
        except Exception as error: record_metric('chat',started,False,error=error); raise
    async def tts(request):
        started=time.perf_counter()
        body = await request.json()
        try:
            audio=await services.synthesize(body.get('text')); record_metric('tts',started,True,characters=len(body.get('text') or ''),audio_bytes=len(audio)); return web.Response(body=audio, content_type='audio/wav')
        except Exception as error: record_metric('tts',started,False,error=error); raise
    async def stt(request):
        started=time.perf_counter()
        audio = await request.read()
        if not audio:
            raise ValueError('Record something first.')
        content_type = request.headers.get('Content-Type', 'audio/webm').split(';')[0]
        extension = {'audio/webm': 'webm', 'audio/ogg': 'ogg', 'audio/mp4': 'm4a', 'audio/wav': 'wav'}.get(content_type)
        if not extension:
            raise ValueError('Unsupported recording format')
        try:
            text=await services.transcribe(audio, f'microphone.{extension}', content_type); record_metric('stt',started,True,audio_bytes=len(audio),output_characters=len(text)); return web.json_response({'text':text})
        except Exception as error: record_metric('stt',started,False,error=error); raise
    async def models(request):
        return web.json_response({'models': await services.models()})
    async def reference(request):
        audio = await request.read()
        if not audio or len(audio) > 5*1024*1024:
            raise ValueError('Upload a WAV reference smaller than 5 MB.')
        with wave.open(io.BytesIO(audio), 'rb') as wav:
            duration = wav.getnframes() / wav.getframerate()
            if wav.getnchannels() not in (1, 2):
                raise ValueError('Use a mono or stereo WAV recording.')
        target = PRIVATE / 'reference.wav'
        target.write_bytes(audio)
        settings.data['reference_audio'] = str(target)
        settings.save()
        return web.json_response({'duration': duration, 'reference_ready': True})
    async def remove_reference(request):
        settings.data.update(reference_audio='', reference_text='')
        settings.save()
        (PRIVATE / 'reference.wav').unlink(missing_ok=True)
        return web.json_response({'reference_ready': False})
    async def bridge_token(request):
        return web.json_response({'token': settings.data['bridge_token']})
    app.router.add_get('/', index)
    app.router.add_get('/performance', performance)
    app.router.add_get('/api/performance', metrics)
    app.router.add_delete('/api/performance', clear_metrics)
    app.router.add_get('/assets/{name}', asset)
    app.router.add_get('/api/status', status)
    app.router.add_post('/api/settings', configure)
    app.router.add_post('/api/chat', chat)
    app.router.add_post('/api/tts', tts)
    app.router.add_post('/api/stt', stt)
    app.router.add_get('/api/models', models)
    app.router.add_post('/api/reference', reference)
    app.router.add_delete('/api/reference', remove_reference)
    app.router.add_get('/api/bridge-token', bridge_token)
    return app

async def main(lan=False, desk_port=8790, offline=False):
    settings = Settings()
    host = '0.0.0.0' if lan else '127.0.0.1'
    async with ClientSession() as session:
        if offline:
            from offline_services import OfflineServices
            services = OfflineServices(settings, session)
        else:
            services = Services(settings, session)
        runners = []
        wyoming = AsyncServer.from_uri(f'tcp://{host}:10700')
        voice_task = None
        try:
            for app, bind, port in ((desk_app(settings, services, lan), '127.0.0.1', desk_port),
                                    (ollama_app(services, settings.data['bridge_token']), host, 11435)):
                runner = web.AppRunner(app, access_log=None)
                await runner.setup()
                runners.append(runner)
                await web.TCPSite(runner, bind, port).start()
            voice_task = asyncio.create_task(wyoming.run(lambda r, w: VoiceHandler(r, w, services)))
            print(f'Lumio test desk: http://localhost:{desk_port}', flush=True)
            print(f'Home Assistant bridges: {host}:10700 (Wyoming), {host}:11435 (Ollama API)', flush=True)
            await voice_task
        finally:
            await wyoming.stop()
            if voice_task:
                voice_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await voice_task
            for runner in reversed(runners):
                await runner.cleanup()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--lan', action='store_true', help='Expose voice bridges to your trusted home network')
    parser.add_argument('--desk-port', type=int, default=8790, help='Loopback settings desk port')
    parser.add_argument('--offline', action='store_true', help='Use only downloaded local models')
    args = parser.parse_args()
    try:
        asyncio.run(main(args.lan, args.desk_port, args.offline))
    except KeyboardInterrupt:
        pass
