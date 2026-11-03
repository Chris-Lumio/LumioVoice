"""Hosted speech and chat services, shared by the UI and Home Assistant bridges."""
import asyncio
import json
import re
from pathlib import Path
import aiohttp
from gradio_client import Client, handle_file
from config import LEBANESE_PROMPT, PRIVATE

GROQ_URL = 'https://api.groq.com/openai/v1'

def prune_completed_tool_history(messages, max_completed=4):
    """Keep prior dialogue, but not stale device snapshots or unfinished actions."""
    starts = [i for i, message in enumerate(messages) if message.get('role') == 'user']
    if len(starts) < 2:
        return messages
    result = list(messages[:starts[0]])
    turns = [messages[start:end] for start, end in zip(starts, starts[1:] + [len(messages)])]
    for turn in turns[:-1][-max_completed:]:
        answers = [m for m in turn[1:] if m.get('role') == 'assistant'
                   and not m.get('tool_calls') and m.get('content')]
        if answers:
            result.extend(m for i, m in enumerate(turn)
                          if i == 0 or m.get('role') == 'system' or m is answers[-1])
        else:
            # A new request must not implicitly resume a previous action whose
            # final confirmation failed or was cancelled.
            result.extend(m for m in turn if m.get('role') == 'system')
    result.extend(turns[-1])  # Preserve the entire active tool loop.
    return result

def compact_tools(tools):
    """Remove schema annotations, retaining parameter constraints and units."""
    def schema(value):
        if isinstance(value, list):
            return [schema(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            if key in ('title', 'examples', '$comment'):
                continue
            if key == 'description':
                # Numeric/unit guidance may be the only place an intent states
                # its units; preserve it even when it is not a schema constraint.
                if isinstance(item, str) and re.search(r'\d|percent|celsius|fahrenheit|kelvin|seconds|minutes', item, re.I):
                    result[key] = item
                continue
            # Property names are data, even if named "description" or "title".
            if key in ('enum', 'const', 'default', 'dependentRequired'):
                result[key] = item
            elif key in ('properties', '$defs', 'definitions', 'patternProperties', 'dependentSchemas'):
                result[key] = {name: schema(spec) for name, spec in item.items()}
            else:
                result[key] = schema(item)
        return result
    result = []
    for tool in tools:
        function = tool['function']
        compact = {key: value for key, value in function.items() if key not in ('parameters', 'description')}
        if function.get('description'):
            compact['description'] = function['description']
        if 'parameters' in function:
            compact['parameters'] = schema(function['parameters'])
        result.append({**tool, 'function': compact})
    return result

def to_provider_messages(messages):
    result = [{'role': 'system', 'content': LEBANESE_PROMPT}]
    pending = []
    for index, original in enumerate(messages):
        role = original.get('role')
        if role not in ('system', 'user', 'assistant', 'tool'):
            raise ValueError('Unsupported message role')
        if original.get('images'):
            raise ValueError('This voice bridge does not support image attachments')
        message = {'role': role, 'content': original.get('content') or ''}
        if role == 'assistant' and original.get('tool_calls'):
            calls = []
            for n, call in enumerate(original['tool_calls']):
                function = call['function']
                call_id = f'call_{index}_{n}'
                args = function.get('arguments', {})
                calls.append({'id': call_id, 'type': 'function', 'function': {
                    'name': function['name'],
                    'arguments': args if isinstance(args, str) else json.dumps(args)}})
                pending.append(call_id)
            message['tool_calls'] = calls
        elif role == 'tool':
            if not pending:
                raise ValueError('Tool result has no preceding tool call')
            message['tool_call_id'] = pending.pop(0)
        result.append(message)
    return result

def from_provider_message(message):
    result = {'role': 'assistant', 'content': message.get('content') or ''}
    if message.get('tool_calls'):
        result['tool_calls'] = []
        for call in message['tool_calls']:
            function = call['function']
            arguments = function.get('arguments') or '{}'
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            if not isinstance(arguments, dict):
                raise ValueError('AI returned invalid device-tool arguments')
            result['tool_calls'].append({'function': {'name': function['name'], 'arguments': arguments}})
    return result

class Services:
    def __init__(self, settings, session):
        self.settings = settings
        self.session = session
        self.tts_lock = asyncio.Lock()
        self.chat_request_lock = asyncio.Lock()
        self.client = None
        self.client_token = None

    async def groq(self, route, *, data=None, body=None, method='POST'):
        if route == '/chat/completions':
            async with self.chat_request_lock:
                return await self._groq_request(route, data=data, body=body, method=method)
        return await self._groq_request(route, data=data, body=body, method=method)

    async def _groq_request(self, route, *, data=None, body=None, method='POST'):
        key = self.settings.data['groq_key']
        if not key:
            raise ValueError('Add a Groq API key in Settings to enable listening and AI replies.')
        for attempt in range(2):
            async with self.session.request(method, GROQ_URL + route,
                    headers={'Authorization': f'Bearer {key}'}, json=body, data=data,
                    timeout=aiohttp.ClientTimeout(total=90)) as response:
                payload = await response.json(content_type=None)
                if response.status < 400:
                    return payload
                detail = payload.get('error', {}).get('message', 'Request failed')
                retry_after = response.headers.get('Retry-After', '')
                if not retry_after:
                    match = re.search(r'try again in ([\d.]+)s', detail, re.I)
                    retry_after = match.group(1) if match else ''
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = -1
                # Retrying AI inference does not replay a Home Assistant action:
                # tools execute outside this HTTP request, in Home Assistant.
                # Never retry audio uploads or switch to a paid provider.
                if not (response.status == 429 and route == '/chat/completions'
                        and attempt == 0 and 0 <= delay <= 60):
                    raise ValueError(f'Groq ({response.status}): {detail}')
            await asyncio.sleep(delay + 0.25)

    async def models(self):
        payload = await self.groq('/models', method='GET')
        return sorted(item['id'] for item in payload['data'])

    async def chat(self, messages, tools=None):
        if not isinstance(messages, list) or not messages or len(messages) > 100:
            raise ValueError('Provide between one and one hundred conversation messages')
        trimmed = prune_completed_tool_history(messages)
        converted = to_provider_messages(trimmed)
        if sum(item['role'] == 'system' for item in converted) > 1:
            converted.pop(0)  # The Lebanese instruction is appended below once.
        last_system = next(i for i in range(len(converted)-1, -1, -1) if converted[i]['role'] == 'system')
        converted[last_system]['content'] += '\n\n' + LEBANESE_PROMPT
        if not tools:
            converted[last_system]['content'] += (
                '\nNo device tools or device states are connected to this conversation. '
                'Do not offer to read home/device status or control appliances. '
                'If asked how you can help at home, offer conversation, explanations, or planning, '
                'and briefly say device control is not connected yet. '
                'Example Lebanese answer: فيني ساعدك بالأسئلة وترتيب نهارك، '
                'بس التحكّم بأجهزة البيت مش موصول هلّق.'
            )
        body = {'model': self.settings.data['chat_model'],
                'messages': converted, 'max_completion_tokens': 1024,
                'temperature': 0.4, 'stream': False}
        if tools:
            # Ollama tool-result messages omit call IDs. Serialize tool calls so
            # results can always be associated with the correct device command.
            body.update(tools=compact_tools(tools), tool_choice='auto', parallel_tool_calls=False)
        payload = await self.groq('/chat/completions', body=body)
        # No messages, names, or credentials are included in these diagnostics.
        metrics = {'model': body['model'], 'tool_count': len(tools or []),
                   'history_messages_before': len(messages), 'history_messages_after': len(trimmed),
                   'original_tools_chars': len(json.dumps(tools or [])),
                   'sent_tools_chars': len(json.dumps(body.get('tools', []))),
                   'usage': payload.get('usage', {})}
        PRIVATE.mkdir(exist_ok=True)
        (PRIVATE / 'last-request-metrics.json').write_text(json.dumps(metrics), encoding='utf-8')
        return from_provider_message(payload['choices'][0]['message'])

    async def transcribe(self, audio, filename='recording.wav', content_type='audio/wav'):
        form = aiohttp.FormData()
        form.add_field('file', audio, filename=filename, content_type=content_type)
        form.add_field('model', self.settings.data['stt_model'])
        form.add_field('language', 'ar')
        form.add_field('prompt', 'محادثة باللهجة اللبنانية. ضوّ الصالون، المكيّف، هلّق، بدّك، شو، طفي، شغّل.')
        payload = await self.groq('/audio/transcriptions', data=form)
        return payload['text'].strip()

    def _synthesize(self, text):
        cfg = self.settings.data.copy()
        token = cfg['hf_token'] or None
        if self.client is None or token != self.client_token:
            self.client = Client(cfg['space'], token=token, verbose=False,
                                 analytics_enabled=False, download_files=str(PRIVATE / 'audio'))
            self.client_token = token
        common = dict(text=text, lang='Levantine Arabic', ns=16, gs=2.0, dn=True,
                      sp=1.0, du=None, pp=True, po=True)
        if cfg['reference_audio']:
            job = self.client.submit(**common, ref_aud=handle_file(cfg['reference_audio']),
                ref_text=cfg['reference_text'], instruct='', api_name='/_clone_fn')
        else:
            job = self.client.submit(**common, param_9=cfg['gender'], param_10='Auto',
                param_11='Auto', param_12='Auto', param_13='Auto', param_14='Auto',
                api_name='/_design_fn')
        try:
            result = job.result(timeout=180)
        except TimeoutError:
            job.cancel()
            raise ValueError('OmniVoice queue timed out. Try again later.') from None
        if not result or not result[0]:
            raise ValueError('OmniVoice returned no audio: ' + str(result[1] if result else 'empty response'))
        path = result[0]
        if isinstance(path, dict):
            path = path.get('path')
        audio = Path(path).read_bytes()
        if not audio.startswith(b'RIFF'):
            raise ValueError('OmniVoice returned an unsupported audio format; expected WAV')
        return audio

    async def synthesize(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 1500:
            raise ValueError('Enter between one and fifteen hundred characters')
        async with self.tts_lock:
            try:
                return await asyncio.to_thread(self._synthesize, text)
            except Exception as error:
                detail = str(error)
                for name in ('groq_key', 'hf_token', 'bridge_token'):
                    secret = self.settings.data.get(name)
                    if secret:
                        detail = detail.replace(secret, '[redacted]')
                PRIVATE.mkdir(exist_ok=True)
                (PRIVATE / 'last-voice-error.json').write_text(json.dumps({'error':detail}),encoding='utf-8')
                raise
