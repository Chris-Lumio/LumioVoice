"""Home Assistant's native Wyoming and Ollama protocols over hosted APIs."""
import io
import wave
from datetime import datetime, timezone
from aiohttp import web
from wyoming.event import Event
from wyoming.server import AsyncEventHandler

VOICE = 'lumio-lebanese'

def service_info():
    def program(name, models, external=False):
        result = {'name': name, 'description': 'Hosted API bridge; internet required',
                  'attribution': {'name': 'Lumio', 'url': 'https://github.com/Oddadmix/Lahgtna-OmniVoice'},
                  'installed': True, 'models': models, 'version': '0.1.0'}
        if external:
            result['requires_external_vad'] = True
        return result
    def model(name):
        return {'name': name, 'description': 'Lebanese Arabic target', 'languages': ['ar'],
                'attribution': {'name': 'Lumio API bridge', 'url': 'https://huggingface.co/spaces/k2-fsa/OmniVoice'},
                'installed': True, 'version': '0.1.0'}
    speaking = program('lumio-speaking', [])
    speaking['voices'] = [model(VOICE)]
    del speaking['models']
    return {'asr': [program('lumio-listening', [model('groq-whisper-ar')], True)],
            'tts': [speaking]}

class VoiceHandler(AsyncEventHandler):
    def __init__(self, reader, writer, services):
        super().__init__(reader, writer)
        self.services = services
        self.audio = bytearray()
        self.format = None
        self.transcribing = False

    async def handle_event(self, event):
        try:
            if event.type == 'describe':
                await self.write_event(Event(type='info', data=service_info()))
            elif event.type == 'transcribe':
                self.audio.clear()
                self.format = None
                self.transcribing = True
            elif event.type == 'audio-start' and self.transcribing:
                self.format = event.data
            elif event.type == 'audio-chunk' and self.transcribing:
                self.format = self.format or event.data
                if len(self.audio) + len(event.payload or b'') > 10 * 1024 * 1024:
                    raise ValueError('Recording too long (10 MB maximum)')
                self.audio.extend(event.payload or b'')
            elif event.type == 'audio-stop' and self.transcribing:
                if not self.format or not self.audio:
                    raise ValueError('No microphone audio received')
                buffer = io.BytesIO()
                with wave.open(buffer, 'wb') as wav:
                    wav.setnchannels(self.format['channels'])
                    wav.setsampwidth(self.format['width'])
                    wav.setframerate(self.format['rate'])
                    wav.writeframes(self.audio)
                text = await self.services.transcribe(buffer.getvalue())
                await self.write_event(Event(type='transcript', data={'text': text, 'language': 'ar'}))
                self.audio.clear()
                self.transcribing = False
            elif event.type == 'synthesize':
                audio = await self.services.synthesize(event.data.get('text', ''))
                with wave.open(io.BytesIO(audio), 'rb') as wav:
                    fmt = {'rate': wav.getframerate(), 'width': wav.getsampwidth(), 'channels': wav.getnchannels()}
                    await self.write_event(Event(type='audio-start', data=fmt))
                    while chunk := wav.readframes(4096):
                        await self.write_event(Event(type='audio-chunk', data=fmt, payload=chunk))
                    await self.write_event(Event(type='audio-stop'))
        except Exception as error:
            self.audio.clear()
            self.transcribing = False
            await self.write_event(Event(type='error', data={'text': str(error), 'code': 'api_error'}))
            # Home Assistant's audio consumer may not handle a generic error
            # event; EOF is required to end the failed audio operation.
            return False
        return True

def ollama_app(services, token):
    @web.middleware
    async def auth(request, handler):
        import secrets
        supplied = request.headers.get('Authorization', '').removeprefix('Bearer ')
        if not secrets.compare_digest(supplied, token):
            return web.json_response({'error': 'Enter the Lumio bridge token in the Ollama API Key field.'}, status=401)
        try:
            return await handler(request)
        except Exception as error:
            return web.json_response({'error': str(error)}, status=502)

    app = web.Application(middlewares=[auth], client_max_size=2*1024*1024)
    async def tags(request):
        return web.json_response({'models': [{'name': VOICE, 'model': VOICE, 'size': 0,
            'digest': 'hosted-api', 'modified_at': '2026-10-27T00:00:00Z',
            'details': {'format': 'api', 'family': 'lumio', 'parameter_size': 'remote', 'quantization_level': 'remote'}}]})
    async def show(request):
        return web.json_response({'capabilities': ['completion', 'tools'], 'parameters': '',
                                 'model_info': {'general.architecture': 'lumio', 'lumio.context_length': 32768},
                                 'details': {'family': 'lumio'}})
    async def chat(request):
        body = await request.json()
        if body.get('model') not in (VOICE, VOICE + ':latest'):
            return web.json_response({'error': 'Choose lumio-lebanese as the model.'}, status=404)
        message = await services.chat(body.get('messages'), body.get('tools'))
        payload = {'model': VOICE, 'created_at': datetime.now(timezone.utc).isoformat(),
                   'message': message, 'done': True, 'done_reason': 'stop'}
        if body.get('stream', True):
            import json
            return web.Response(text=json.dumps(payload, ensure_ascii=False)+'\n', content_type='application/x-ndjson')
        return web.json_response(payload)
    async def version(request):
        return web.json_response({'version': '0.13.0'})
    app.router.add_get('/api/tags', tags)
    app.router.add_post('/api/show', show)
    app.router.add_post('/api/chat', chat)
    app.router.add_get('/api/version', version)
    return app
