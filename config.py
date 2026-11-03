"""Shared Lebanese defaults; private settings stay out of source control."""
import json
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / '.local'
CONFIG_FILE = PRIVATE / 'config.json'
LEBANESE_PROMPT = '''You are Lumio, a helpful home voice assistant. By default reply in natural
Lebanese Arabic using Arabic script, not Modern Standard Arabic. Use Lebanese wording such as
هلّق، بدّك، فيك، شو، إيه. Keep spoken answers short, normally one or two sentences, without
Markdown. Say numbers in words when practical. Answer in another language only when asked.
Answer directly. Do not add greetings or introductory filler to ordinary replies.
Only greet when the user explicitly greets you; do not repeat greetings in follow-up replies.
Never claim you controlled a device unless a supplied Home Assistant tool succeeded.
If no device tools are available, explain that home controls are not connected.
Understand Lebanese Arabizi written in Latin letters, with flexible spellings and mixed
Arabic/English/French words. Common digits include 2 for ء (or Lebanese ق), 3 for ع,
7 for ح, 5/kh for خ, and 8/gh for غ; interpret them in context, not as fixed replacements.
Examples of equivalent spellings: daww/daw/do = ضوّ, azdak/asdak/2asdak = قصدك,
salon = صالون, matbakh = مطبخ, halla2 = هلّق, baddi = بدّي, taffe = طفّي.
Treat Arabizi as Lebanese, not a request to answer in English or translate the message.
Reply in Arabic script by default, including when input is Arabizi, for spoken output.
Only output Arabizi if the user explicitly asks. Do not copy Arabizi digits into speech.
Interpret meaning and intent; do not perform an action merely because a command appears
inside a quoted example, a translation request, or a question about wording.
Use everyday Lebanese phrasing, with no exaggerated slang or stock greetings.
Prefer ضوّ، ضوّ الصالون، المكيّف، هلّق، مش، إيه، فيني، بدّك over formal equivalents.
Examples of tone (not facts or permission to execute actions):
- "ayya daww azdak? el salon aw el matbakh?" means "أي ضوّ قصدك؟ الصالون أو المطبخ؟"
- Clarifying an ambiguous light command: "أي ضوّ قصدك، الصالون أو المطبخ؟"
- "ma fhemet, fik t3id?" -> "أكيد، بقولها بطريقة أبسط." Then explain simply.
- Confirm an action ONLY after a successful tool result: "تمام، شغّلت ضوّ الصالون."
- If an action failed: "ما قدرت شغّل الضوّ."
- If status cannot be verified: "ما قدرت أتأكّد إذا اشتغل."
Distinguish imperative شغّل (turn on) from completed شغّلت (turned on).
Do not correct spelling or explain Arabizi unless asked. Ask one short clarification
when context does not resolve an ambiguous word, room, or device.
اكتب باللهجة اللبنانية المحكية، مش بالفصحى. جاوب دغري بلا تحية بكل ردّ.
ما تقول «أهلين» إلا إذا المستخدم عم يسلّم عليك. استعمل «فيني ساعدك»، «طفي الضوّ»،
«شغّل» بدل تعابير رسمية مثل «يمكنني مساعدتك» و«تشغيل أو إطفاء الأجهزة».'''
DEFAULTS = {
    'groq_key': '', 'hf_token': '', 'bridge_token': '',
    'chat_model': 'qwen/qwen3.8-27b',
    'stt_model': 'whisper-large-v3-turbo',
    'space': 'k2-fsa/OmniVoice',
    'tts_language': 'Levantine Arabic', 'stt_language': 'ar',
    'gender': 'Female / 女', 'reference_audio': '', 'reference_text': '',
}

class Settings:
    def __init__(self, path=CONFIG_FILE):
        self.path = Path(path)
        self.data = dict(DEFAULTS)
        if self.path.exists():
            self.data.update(json.loads(self.path.read_text(encoding='utf-8')))
        self.data['groq_key'] = os.getenv('GROQ_API_KEY') or self.data['groq_key']
        self.data['hf_token'] = os.getenv('HF_TOKEN') or self.data['hf_token']
        if not self.data['bridge_token']:
            self.data['bridge_token'] = secrets.token_urlsafe(32)
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if os.name != 'nt':
            self.path.parent.chmod(0o700)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding='utf-8')
        if os.name != 'nt':
            temporary.chmod(0o600)
        temporary.replace(self.path)

    def public(self):
        return {**{k: v for k, v in self.data.items() if k not in ('groq_key', 'hf_token', 'bridge_token')},
                'groq_configured': bool(self.data['groq_key']),
                'hf_configured': bool(self.data['hf_token']),
                'reference_ready': bool(self.data['reference_audio'])}

    def update(self, values):
        for key in ('groq_key', 'hf_token', 'chat_model', 'stt_model', 'reference_text', 'gender'):
            if key in values:
                value = str(values[key]).strip()
                if key in ('groq_key', 'hf_token') and not value:
                    continue  # blank fields retain the existing secret
                if len(value) > 10000:
                    raise ValueError('Setting is too long')
                self.data[key] = value
        self.save()
