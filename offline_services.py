"""Local-only inference. No provider calls or runtime model downloads."""
import asyncio
import io
import json
import os
import re
from pathlib import Path

# Set before importing model libraries. Missing files must fail, never download.
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['GRADIO_ANALYTICS_ENABLED'] = 'False'

from config import PRIVATE
from services import Services

MODELS = PRIVATE / 'models'

class OfflineServices(Services):
    offline = True

    def __init__(self, settings, session):
        super().__init__(settings, session)
        self.inference_lock = asyncio.Lock()
        self.chat_model = self.tokenizer = self.whisper = self.voice = None
        self.reference_key = self.reference_prompt = None

    async def models(self):
        return ['local-qwen3-1.7b', 'local-whisper-small']

    async def groq(self, route, *, data=None, body=None, method='POST'):
        if route != '/chat/completions':
            raise ValueError('Online provider requests are disabled in offline mode.')
        async with self.inference_lock:
            message = await asyncio.to_thread(self._chat, body)
        return {'choices': [{'message': message}], 'usage': {}}

    def _chat(self, body):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        torch.set_num_threads(6)
        if self.chat_model is None:
            # 8-bit keeps Qwen beside OmniVoice on a 6 GB GPU; consumer CPUs
            # lack native bfloat16, so the CPU fallback uses float32.
            gpu = torch.cuda.is_available()
            print(f'Loading local Qwen on {"GPU (8-bit)" if gpu else "CPU"}...', flush=True)
            self.tokenizer = AutoTokenizer.from_pretrained(MODELS / 'chat', local_files_only=True)
            self.tokenizer.truncation_side = 'left'
            if gpu:
                from transformers import BitsAndBytesConfig
                options = {'quantization_config': BitsAndBytesConfig(load_in_8bit=True),
                           'dtype': torch.float16, 'device_map': 'cuda:0'}
            else:
                options = {'dtype': torch.float32, 'device_map': 'cpu'}
            self.chat_model = AutoModelForCausalLM.from_pretrained(
                MODELS / 'chat', local_files_only=True, **options).eval()
        prompt = self.tokenizer.apply_chat_template(
            body['messages'], tools=body.get('tools'), tokenize=False,
            add_generation_prompt=True, enable_thinking=False)
        inputs = self.tokenizer(prompt, return_tensors='pt', truncation=True,
                                max_length=6144).to(self.chat_model.device)
        with torch.inference_mode():
            output = self.chat_model.generate(
                **inputs, max_new_tokens=180, do_sample=True, temperature=0.6,
                top_p=0.8, top_k=20, repetition_penalty=1.1,
                pad_token_id=self.tokenizer.eos_token_id)
        text = self.tokenizer.decode(output[0, inputs.input_ids.shape[1]:], skip_special_tokens=True)
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
        calls = re.findall(r'<tool_call>\s*(.*?)\s*</tool_call>', text, flags=re.S)
        result = {'role': 'assistant', 'content': re.sub(
            r'<tool_call>.*?</tool_call>', '', text, flags=re.S).strip()}
        if calls:
            if not body.get('tools'):
                raise ValueError('The local model attempted an unavailable device tool.')
            allowed = {t['function']['name'] for t in body['tools']}
            result['tool_calls'] = []
            for i, raw in enumerate(calls):
                call = json.loads(raw)
                if call['name'] not in allowed or not isinstance(call.get('arguments'), dict):
                    raise ValueError('The local model returned an invalid device tool.')
                result['tool_calls'].append({'id': f'local_{i}', 'type': 'function',
                    'function': {'name': call['name'], 'arguments': json.dumps(call['arguments'])}})
        if not result['content'] and not calls:
            raise ValueError('The local model returned an empty reply. Try a shorter question.')
        return result

    def _transcribe(self, audio):
        from faster_whisper import WhisperModel
        if self.whisper is None:
            print('Loading local Whisper on CPU...', flush=True)
            self.whisper = WhisperModel(str(MODELS / 'whisper'), device='cpu',
                                        compute_type='int8', cpu_threads=4,
                                        local_files_only=True)
        segments, _ = self.whisper.transcribe(io.BytesIO(audio), language='ar',
            beam_size=5, vad_filter=True,
            initial_prompt='محادثة باللهجة اللبنانية. ضوّ الصالون، المكيّف، هلّق، بدّك، شو، طفي، شغّل.')
        return ' '.join(segment.text.strip() for segment in segments).strip()

    async def transcribe(self, audio, filename='recording.wav', content_type='audio/wav'):
        async with self.inference_lock:
            return await asyncio.to_thread(self._transcribe, audio)

    def _synthesize(self, text):
        import torch
        import soundfile as sf
        from omnivoice import OmniVoice, OmniVoiceGenerationConfig
        if self.voice is None:
            if not torch.cuda.is_available():
                raise ValueError('Local OmniVoice requires the installed NVIDIA CUDA runtime.')
            print('Loading local OmniVoice on GPU...', flush=True)
            self.voice = OmniVoice.from_pretrained(str(MODELS / 'voice'),
                device_map='cuda:0', dtype=torch.float16, load_asr=False,
                local_files_only=True)
        cfg = self.settings.data
        kwargs = {}
        if cfg['reference_audio']:
            reference = Path(cfg['reference_audio'])
            transcript = cfg['reference_text'].strip()
            if not transcript:
                transcript = self._transcribe(reference.read_bytes())
                if not transcript:
                    raise ValueError('Could not transcribe the reference; enter its exact transcript.')
            key = (str(reference), reference.stat().st_mtime_ns, transcript)
            if key != self.reference_key:
                self.reference_prompt = self.voice.create_voice_clone_prompt(
                    ref_audio=str(reference), ref_text=transcript)
                self.reference_key = key
            kwargs['voice_clone_prompt'] = self.reference_prompt
        with torch.inference_mode():
            audio = self.voice.generate(text=text, language='Levantine Arabic',
                generation_config=OmniVoiceGenerationConfig(num_step=32, guidance_scale=2.0),
                **kwargs)[0]
        out = io.BytesIO()
        sf.write(out, audio, self.voice.sampling_rate, format='WAV', subtype='PCM_16')
        return out.getvalue()

    async def synthesize(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 1500:
            raise ValueError('Enter between one and fifteen hundred characters')
        async with self.inference_lock:
            return await asyncio.to_thread(self._synthesize, text)
