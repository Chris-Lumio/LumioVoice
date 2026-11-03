"""LumioSolutions Voice Studio: a local web interface for the OmniVoice engine."""
import os

# Set before importing model libraries. Missing files must fail, never download.
for _key, _value in {'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                     'HF_HUB_DISABLE_TELEMETRY': '1', 'GRADIO_ANALYTICS_ENABLED': 'False'}.items():
    os.environ.setdefault(_key, _value)

import argparse
import asyncio
import hashlib
import io
import json
import re
import time
import urllib.parse
from collections import OrderedDict
from pathlib import Path
from aiohttp import web
from arabizi import convert as convert_arabizi

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
PRIVATE = PROJECT / '.local'
MODELS = PRIVATE / 'models'
WORK = PRIVATE / 'studio'
STATIC = ROOT / 'static'
TAUGHT_WORDS = PRIVATE / 'arabizi-words.json'  # spellings the user taught the converter
ARABIZI_WORD = re.compile(r"[a-z0-9']{1,40}")
ARABIC_WORD = re.compile(r'[ء-ْ٠-٩ ]{1,60}')
MAX_TEXT = 2000
MAX_REFERENCE = 10 * 1024 * 1024

# Voice Design attributes, in the English wording the model expects.
ATTRIBUTES = {
    'gender': ['Male', 'Female'],
    'age': ['Child', 'Teenager', 'Young Adult', 'Middle-aged', 'Elderly'],
    'pitch': ['Very Low Pitch', 'Low Pitch', 'Moderate Pitch', 'High Pitch', 'Very High Pitch'],
    'style': ['Whisper'],
    'accent': ['American Accent', 'Australian Accent', 'British Accent', 'Canadian Accent',
               'Chinese Accent', 'Indian Accent', 'Japanese Accent', 'Korean Accent',
               'Portuguese Accent', 'Russian Accent'],
}


class Engine:
    """Owns the GPU model; all inference is serialized through one lock."""

    def __init__(self, device):
        self.device = device
        self.model = None
        self.state, self.error = 'loading', None
        self.has_asr = (MODELS / 'asr' / 'model.safetensors').exists()
        self.lock = asyncio.Lock()
        self.prompts = OrderedDict()  # cached voice-clone prompts, newest last
        self.gpu = ''

    def load(self):
        import torch
        from omnivoice import OmniVoice
        try:
            if self.device.startswith('cuda'):
                if not torch.cuda.is_available():
                    raise RuntimeError('No NVIDIA GPU is available to run OmniVoice.')
                self.gpu = torch.cuda.get_device_name(0)
            elif self.device == 'cpu':
                self.gpu = 'CPU (Multi-thread ARM/x86)'
            dtype = torch.float32 if self.device == 'cpu' else torch.float16
            options = {'device_map': self.device, 'dtype': dtype, 'local_files_only': True,
                       'load_asr': self.has_asr}
            if self.has_asr:
                options['asr_model_name'] = str(MODELS / 'asr')
            self.model = OmniVoice.from_pretrained(str(MODELS / 'voice'), **options)
            self.state = 'ready'
        except Exception as error:
            self.state, self.error = 'error', f'{type(error).__name__}: {error}'
        print(f'Voice engine {self.state}' + (f': {self.error}' if self.error else ''), flush=True)

    def _require(self):
        if self.state != 'ready':
            raise ValueError(self.error or 'The voice engine is still warming up. Try again in a moment.')

    def _reference_file(self, audio):
        import soundfile as sf
        digest = hashlib.sha256(audio).hexdigest()
        path = WORK / f'{digest}.wav'
        if not path.exists():
            WORK.mkdir(parents=True, exist_ok=True)
            path.write_bytes(audio)
        try:
            info = sf.info(str(path))
        except Exception:
            path.unlink(missing_ok=True)
            raise ValueError('The reference recording could not be read. Use a WAV file.')
        if not 1 <= info.duration <= 30:
            raise ValueError('Use a reference recording between 1 and 30 seconds long.')
        return digest, path

    def _listen(self, path):
        import soundfile as sf
        # Whisper's file-path input needs ffmpeg, so hand it decoded samples.
        samples, rate = sf.read(str(path), dtype='float32', always_2d=True)
        return self.model.transcribe((samples.mean(axis=1), rate)).strip()

    def transcribe(self, audio):
        self._require()
        if not self.has_asr:
            raise ValueError('Automatic transcription is not installed. Type the transcript instead.')
        _, path = self._reference_file(audio)
        return self._listen(path)

    def generate(self, params, reference):
        import numpy as np
        import soundfile as sf
        from omnivoice import OmniVoiceGenerationConfig
        self._require()
        config = OmniVoiceGenerationConfig(
            num_step=params['steps'], guidance_scale=params['guidance'], denoise=params['denoise'],
            preprocess_prompt=params['preprocess'], postprocess_output=params['postprocess'],
            t_shift=params['t_shift'], layer_penalty_factor=params['layer_penalty'],
            position_temperature=params['pos_temp'], class_temperature=params['class_temp'],
            audio_chunk_duration=params['chunk_duration'])
        kwargs = {'text': params['text'], 'generation_config': config,
                  'language': None if params['language'] == 'Auto' else params['language'],
                  'normalize_text': params.get('normalize_text', False)}
        if params['duration']:
            kwargs['duration'] = params['duration']
        elif params['speed'] != 1.0:
            kwargs['speed'] = params['speed']
        if params['instruct']:
            kwargs['instruct'] = params['instruct']
        transcript = params['transcript']
        if params['mode'] == 'clone':
            if not reference:
                raise ValueError('Add a reference voice first: upload, record, or pick the Lumio voice.')
            digest, path = self._reference_file(reference)
            if not transcript:
                if not self.has_asr:
                    raise ValueError('Type exactly what the reference recording says.')
                transcript = self._listen(path)
            key = (digest, transcript, params['preprocess'])
            if key not in self.prompts:
                self.prompts[key] = self.model.create_voice_clone_prompt(
                    ref_audio=str(path), ref_text=transcript, preprocess_prompt=params['preprocess'])
                while len(self.prompts) > 8:
                    self.prompts.popitem(last=False)
            self.prompts.move_to_end(key)
            kwargs['voice_clone_prompt'] = self.prompts[key]
        audio = self.model.generate(**kwargs)[0]
        output = io.BytesIO()
        sf.write(output, np.clip(audio, -1, 1), self.model.sampling_rate, format='WAV', subtype='PCM_16')
        return output.getvalue(), len(audio) / self.model.sampling_rate, transcript


def number(form, key, default, low, high, kind=float):
    raw = form.get(key, '')
    if raw in ('', None):
        return default
    try:
        value = kind(float(raw))
    except ValueError:
        raise ValueError(f'{key} must be a number')
    if not low <= value <= high:
        raise ValueError(f'{key} must be between {low} and {high}')
    return value


def flag(form, key, default=True):
    return form.get(key, str(default).lower()) in ('true', '1', 'on')


def build_instruct(form):
    chosen = []
    for group, options in ATTRIBUTES.items():
        value = form.get(group, '')
        if value:
            if value not in options:
                raise ValueError(f'Unknown {group} option')
            chosen.append(value)
    return ', '.join(chosen)


@web.middleware
async def guard(request, handler):
    # The studio is a single-user local tool; refuse other hosts and origins.
    if request.host.split(':')[0] not in ('127.0.0.1', 'localhost'):
        raise web.HTTPForbidden(text='Open the studio through localhost.')
    origin = request.headers.get('Origin')
    if origin and origin != 'http://' + request.host:
        raise web.HTTPForbidden(text='Cross-origin requests are not allowed.')
    try:
        response = await handler(request)
    except web.HTTPException:
        raise
    except ValueError as error:
        response = web.json_response({'error': str(error)}, status=400)
    except Exception as error:
        response = web.json_response({'error': f'{type(error).__name__}: {error}'}, status=500)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; "
        "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
    return response


def studio_app(engine):
    from omnivoice.utils.lang_map import LANG_NAMES, lang_display_name
    languages = sorted(lang_display_name(name) for name in LANG_NAMES)
    config_file = PRIVATE / 'config.json'

    def preset():
        # The Lumio desk's saved reference voice, if one exists.
        if not config_file.exists():
            return None
        data = json.loads(config_file.read_text(encoding='utf-8'))
        path = Path(data.get('reference_audio') or '')
        if path.is_file() and data.get('reference_text', '').strip():
            return path, data['reference_text'].strip()
        return None

    async def index(request):
        return web.FileResponse(STATIC / 'index.html')

    async def asset(request):
        name = request.match_info['name']
        if name not in ('studio.css', 'studio.js', 'logo.svg'):
            raise web.HTTPNotFound()
        return web.FileResponse(STATIC / name)

    async def info(request):
        saved = preset()
        return web.json_response({
            'state': engine.state, 'error': engine.error, 'gpu': engine.gpu,
            'auto_transcribe': engine.has_asr, 'languages': languages, 'attributes': ATTRIBUTES,
            'presets': [{'id': 'lumio', 'name': 'Lumio Lebanese', 'transcript': saved[1]}] if saved else []})

    async def preset_audio(request):
        saved = preset()
        if not saved or request.match_info['id'] != 'lumio':
            raise web.HTTPNotFound()
        return web.FileResponse(saved[0], headers={'Content-Type': 'audio/wav'})

    async def read_form(request):
        form, reference = {}, None
        async for part in await request.multipart():
            if part.name == 'reference':
                reference = await part.read(decode=False)
                if len(reference) > MAX_REFERENCE:
                    raise ValueError('The reference recording must be smaller than 10 MB.')
            else:
                form[part.name] = (await part.text())[:MAX_TEXT + 1]
        return form, reference

    taught = {}
    if TAUGHT_WORDS.exists():
        taught.update(json.loads(TAUGHT_WORDS.read_text(encoding='utf-8')))

    def save_taught():
        PRIVATE.mkdir(parents=True, exist_ok=True)
        TAUGHT_WORDS.write_text(json.dumps(taught, indent=2, ensure_ascii=False), encoding='utf-8')

    async def arabizi(request):
        body = await request.json()
        text = body.get('text', '') if isinstance(body, dict) else ''
        if not isinstance(text, str):
            raise ValueError('Send the text to convert.')
        return web.json_response(convert_arabizi(text[:MAX_TEXT], taught))

    async def words(request):
        return web.json_response({'words': taught})

    async def teach(request):
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError('Send the word and its Arabic spelling.')
        word = str(body.get('word', '')).strip().lower()
        arabic = str(body.get('arabic', '')).strip()
        if not ARABIZI_WORD.fullmatch(word):
            raise ValueError('The Arabizi word must be Latin letters and digits only, up to 40 characters.')
        if not ARABIC_WORD.fullmatch(arabic):
            raise ValueError('The spelling must be in Arabic letters, up to 60 characters.')
        taught[word] = arabic
        save_taught()
        return web.json_response({'words': taught})

    async def forget(request):
        word = request.match_info['word'].lower()
        if taught.pop(word, None) is not None:
            save_taught()
        return web.json_response({'words': taught})

    async def transcribe(request):
        _, reference = await read_form(request)
        if not reference:
            raise ValueError('Add a reference recording first.')
        async with engine.lock:
            text = await asyncio.to_thread(engine.transcribe, reference)
        return web.json_response({'transcript': text})

    async def generate(request):
        form, reference = await read_form(request)
        text = form.get('text', '').strip()
        if not text:
            raise ValueError('Write something for the voice to say.')
        if len(text) > MAX_TEXT:
            raise ValueError(f'Keep the script under {MAX_TEXT} characters.')
        language = form.get('language', 'Auto').strip() or 'Auto'
        if language != 'Auto' and language not in languages:
            raise ValueError(f'"{language}" is not a supported language.')
        mode = form.get('mode', 'clone')
        if mode == 'pi5':
            mode = 'clone' if reference else 'design'
        elif mode not in ('clone', 'design'):
            raise ValueError('Unknown mode')
        params = {
            'mode': mode, 'text': text, 'language': language,
            'transcript': form.get('transcript', '').strip() if mode == 'clone' else '',
            'instruct': build_instruct(form) if mode == 'design' else form.get('instruct', '').strip(),
            'steps': number(form, 'steps', 32, 4, 64, int),
            'guidance': number(form, 'guidance', 2.0, 0, 4),
            'speed': number(form, 'speed', 1.0, 0.5, 1.5),
            'duration': number(form, 'duration', 0, 0, 120),
            'denoise': flag(form, 'denoise'), 'preprocess': flag(form, 'preprocess'),
            'postprocess': flag(form, 'postprocess'),
            # Advanced generation parameters (hidden from basic UI, tunable for quality)
            'normalize_text': flag(form, 'normalize_text', False),
            't_shift': number(form, 't_shift', 0.1, 0.0, 1.0),
            'layer_penalty': number(form, 'layer_penalty', 5.0, 0.0, 20.0),
            'pos_temp': number(form, 'pos_temp', 5.0, 0.0, 20.0),
            'class_temp': number(form, 'class_temp', 0.0, 0.0, 2.0),
            'chunk_duration': number(form, 'chunk_duration', 15.0, 5.0, 60.0),
        }
        started = time.perf_counter()
        async with engine.lock:
            audio, seconds, transcript = await asyncio.to_thread(
                engine.generate, params, reference if mode == 'clone' else None)
        return web.Response(body=audio, content_type='audio/wav', headers={
            'X-Audio-Seconds': f'{seconds:.2f}',
            'X-Render-Seconds': f'{time.perf_counter() - started:.2f}',
            'X-Transcript': urllib.parse.quote(transcript or ''),
            'X-Instruct': urllib.parse.quote(params['instruct'] or '')})

    app = web.Application(middlewares=[guard], client_max_size=MAX_REFERENCE + 1024 * 1024)
    app.router.add_get('/', index)
    app.router.add_get('/assets/{name}', asset)
    app.router.add_get('/api/info', info)
    app.router.add_get('/api/presets/{id}', preset_audio)
    app.router.add_post('/api/arabizi', arabizi)
    app.router.add_get('/api/arabizi/words', words)
    app.router.add_post('/api/arabizi/words', teach)
    app.router.add_delete('/api/arabizi/words/{word}', forget)
    app.router.add_post('/api/transcribe', transcribe)
    app.router.add_post('/api/generate', generate)
    return app


async def main(port, device):
    engine = Engine(device)
    runner = web.AppRunner(studio_app(engine), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, '127.0.0.1', port).start()
    print(f'LumioSolutions Voice Studio: http://127.0.0.1:{port}', flush=True)
    try:
        await asyncio.to_thread(engine.load)
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='LumioSolutions Voice Studio')
    parser.add_argument('--port', type=int, default=7860, help='Loopback port (default 7860)')
    parser.add_argument('--device', default='cuda:0', help='Torch device for OmniVoice')
    args = parser.parse_args()
    try:
        asyncio.run(main(args.port, args.device))
    except KeyboardInterrupt:
        pass
