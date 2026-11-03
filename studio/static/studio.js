'use strict';

const $ = (id) => document.getElementById(id);
const TRAIT_LABELS = { gender: 'Gender', age: 'Age', pitch: 'Pitch', style: 'Style', accent: 'Accent' };
const TRAIT_NOTES = { accent: 'English speech only' };
const QUICK_LANGUAGES = ['Levantine Arabic', 'Standard Arabic', 'English', 'French', 'Auto'];
const MAX_RECORD_SECONDS = 30;

const state = {
  mode: 'clone',
  info: null,
  reference: null, // { blob, buffer, name }
  traits: {},
  takes: [],
  current: null,
  busy: false,
  recorder: null,
};
let audioContext;
const context = () => (audioContext ||= new AudioContext());

/* ---------- Helpers ---------- */

function toast(message, kind = 'error') {
  const el = $('toast');
  el.textContent = message;
  el.className = 'toast' + (kind === 'info' ? ' info' : '');
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, kind === 'info' ? 3500 : 7000);
}

const clock = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

async function readError(response) {
  try { return (await response.json()).error || response.statusText; }
  catch { return `${response.status} ${response.statusText}`; }
}

// Decode any browser-playable audio, mix to mono and encode 16-bit WAV so the
// engine only ever receives one well-supported format.
async function toWav(blob) {
  const buffer = await context().decodeAudioData(await blob.arrayBuffer());
  const length = Math.min(buffer.length, buffer.sampleRate * MAX_RECORD_SECONDS);
  const mono = new Float32Array(length);
  for (let c = 0; c < buffer.numberOfChannels; c++) {
    const data = buffer.getChannelData(c);
    for (let i = 0; i < length; i++) mono[i] += data[i] / buffer.numberOfChannels;
  }
  const bytes = new DataView(new ArrayBuffer(44 + length * 2));
  const text = (offset, s) => [...s].forEach((ch, i) => bytes.setUint8(offset + i, ch.charCodeAt(0)));
  text(0, 'RIFF'); bytes.setUint32(4, 36 + length * 2, true); text(8, 'WAVE');
  text(12, 'fmt '); bytes.setUint32(16, 16, true); bytes.setUint16(20, 1, true); bytes.setUint16(22, 1, true);
  bytes.setUint32(24, buffer.sampleRate, true); bytes.setUint32(28, buffer.sampleRate * 2, true);
  bytes.setUint16(32, 2, true); bytes.setUint16(34, 16, true);
  text(36, 'data'); bytes.setUint32(40, length * 2, true);
  for (let i = 0; i < length; i++) {
    const v = Math.max(-1, Math.min(1, mono[i]));
    bytes.setInt16(44 + i * 2, v < 0 ? v * 0x8000 : v * 0x7fff, true);
  }
  const wav = new Blob([bytes], { type: 'audio/wav' });
  return { blob: wav, buffer: await context().decodeAudioData(await wav.arrayBuffer()) };
}

function peaks(buffer, count) {
  const data = buffer.getChannelData(0);
  const step = Math.max(1, Math.floor(data.length / count));
  const out = new Float32Array(count);
  let max = 0;
  for (let i = 0; i < count; i++) {
    let peak = 0;
    for (let j = i * step, end = Math.min(data.length, j + step); j < end; j++) peak = Math.max(peak, Math.abs(data[j]));
    out[i] = peak; max = Math.max(max, peak);
  }
  return out.map((p) => (max ? p / max : 0));
}

function drawWave(canvas, buffer, progress = 0) {
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth, height = canvas.clientHeight;
  if (!width) return;
  canvas.width = width * ratio; canvas.height = height * ratio;
  const g = canvas.getContext('2d');
  g.scale(ratio, ratio);
  const styles = getComputedStyle(document.documentElement);
  const bar = 3, gap = 2, count = Math.floor(width / (bar + gap));
  const values = canvas._peaks?.length === count && canvas._buffer === buffer ? canvas._peaks : peaks(buffer, count);
  canvas._peaks = values; canvas._buffer = buffer;
  const played = styles.getPropertyValue('--accent').trim();
  const rest = styles.getPropertyValue('--wave').trim();
  values.forEach((v, i) => {
    const h = Math.max(2, v * (height - 6));
    g.fillStyle = i / count < progress ? played : rest;
    g.beginPath();
    g.roundRect(i * (bar + gap), (height - h) / 2, bar, h, 1.5);
    g.fill();
  });
}

/* ---------- Engine status & static data ---------- */

async function loadInfo() {
  try {
    const response = await fetch('/api/info');
    state.info = await response.json();
  } catch {
    setStatus('error', 'Studio server is not reachable');
    return setTimeout(loadInfo, 3000);
  }
  const info = state.info;
  if (!$('languages').children.length) {
    $('languages').append(...['Auto', ...info.languages].map((name) => new Option(name)));
    buildTraits(info.attributes);
    $('preset').hidden = !info.presets.length;
    $('transcribe').hidden = !info.auto_transcribe;
    $('transcript-hint').textContent = info.auto_transcribe
      ? 'Leave empty to transcribe automatically. An exact transcript gives the closest match.'
      : 'Required for cloning. Type the exact words spoken in the recording.';
  }
  if (info.state === 'ready') setStatus('ready', 'Voice engine ready');
  else if (info.state === 'error') setStatus('error', info.error);
  else { setStatus('loading', 'Warming up the voice engine…'); setTimeout(loadInfo, 1500); }
  if (info.gpu) $('gpu').textContent = `Running on ${info.gpu}`;
}

function setStatus(kind, text) {
  $('status').dataset.state = kind;
  $('status').lastElementChild.textContent = text;
  $('status').title = text;
}

/* ---------- Modes & traits ---------- */

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll('.mode').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.mode === mode)));
  $('panel-clone').hidden = mode !== 'clone';
  $('panel-design').hidden = mode !== 'design';
  $('panel-pi5').hidden = mode !== 'pi5';
  $('instruct-field').hidden = mode !== 'clone';
  if (mode === 'pi5') {
    applyPi5Tuning(false);
  }
}

function applyPi5Tuning(showToast = true) {
  const PI5_PROFILE = {
    steps: 10,
    guidance: 1.4,
    speed: 1.0,
    t_shift: 0.08,
    layer_penalty: 4.0,
    pos_temp: 2.5,
    class_temp: 0.0,
    chunk_duration: 8,
  };
  for (const [id, val] of Object.entries(PI5_PROFILE)) {
    const el = $(id);
    if (el) { el.value = val; el.dispatchEvent(new Event('input')); }
  }
  $('denoise').checked = false;
  $('preprocess').checked = true;
  $('postprocess').checked = true;
  $('normalize_text').checked = false;
  if (!state.reference && state.info?.presets?.length) {
    usePreset().catch(() => {});
  }
  if (showToast) {
    toast('Pi 5 tuning applied: 10 steps, denoise OFF, 8s chunking.', 'info');
  }
}

function buildTraits(attributes) {
  const root = $('traits');
  for (const [group, options] of Object.entries(attributes)) {
    const wrap = document.createElement('div');
    wrap.className = 'trait';
    const name = document.createElement('span');
    name.className = 'trait-name';
    name.textContent = TRAIT_LABELS[group] || group;
    if (TRAIT_NOTES[group]) name.append(' ', Object.assign(document.createElement('small'), { textContent: `· ${TRAIT_NOTES[group]}` }));
    const chips = document.createElement('div');
    chips.className = 'chips';
    for (const value of ['', ...options]) {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'chip-btn';
      chip.textContent = value || 'Any';
      chip.setAttribute('aria-pressed', String(value === ''));
      chip.addEventListener('click', () => {
        state.traits[group] = value;
        chips.querySelectorAll('.chip-btn').forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
      });
      chips.append(chip);
    }
    wrap.append(name, chips);
    root.append(wrap);
  }
  // A sensible starting voice for the Lebanese demo.
  for (const [group, value] of [['gender', 'Female'], ['age', 'Young Adult']]) {
    [...root.querySelectorAll('.trait')].find((t) => t.firstChild.textContent === TRAIT_LABELS[group])
      ?.querySelectorAll('.chip-btn').forEach((c) => { if (c.textContent === value) c.click(); });
  }
}

function buildQuickLanguages() {
  const root = $('quick-langs');
  for (const name of QUICK_LANGUAGES) {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'chip-btn';
    chip.textContent = name === 'Auto' ? 'Detect automatically' : name;
    chip.dataset.value = name;
    chip.addEventListener('click', () => { $('language').value = name; syncLanguage(); });
    root.append(chip);
  }
  syncLanguage();
}

function syncLanguage() {
  const value = $('language').value.trim();
  $('quick-langs').querySelectorAll('.chip-btn').forEach((c) => c.setAttribute('aria-pressed', String(c.dataset.value === value)));
}

/* ---------- Arabizi ---------- */

const arabizi = { timer: null, forced: false, edited: false, request: 0 };

function arabiziActive() {
  return !$('arabizi').hidden && $('arabizi-on').checked && $('arabic').value.trim() !== '';
}

async function convertArabizi(force = false) {
  const text = $('text').value;
  if (!/[A-Za-z]/.test(text)) {
    $('arabizi').hidden = true;
    $('arabizi-offer').hidden = true;
    arabizi.forced = false;
    return;
  }
  const id = ++arabizi.request;
  let result;
  try {
    const response = await fetch('/api/arabizi', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }),
    });
    if (!response.ok) return;
    result = await response.json();
  } catch { return; }
  if (id !== arabizi.request) return; // a newer conversion is on its way
  const show = result.confident || arabizi.forced;
  $('arabizi').hidden = !show;
  $('arabizi-offer').hidden = show;
  if (!show) return;
  if (force || !arabizi.edited) {
    $('arabic').value = result.arabic;
    arabizi.edited = false;
  }
  const hint = $('arabizi-hint');
  hint.replaceChildren();
  if (result.unknown.length) {
    hint.append('Spelled by rules, not in the dictionary: ');
    result.unknown.forEach((word, i) => {
      if (i) hint.append(', ');
      hint.append(Object.assign(document.createElement('em'), { textContent: word }));
    });
    hint.append('. Check those words before generating.');
  } else {
    hint.textContent = 'Every word was recognised. Edit the Arabic if anything looks off.';
  }
  if (arabizi.edited) {
    hint.append(' ');
    const again = Object.assign(document.createElement('button'), { type: 'button', className: 'link', textContent: 'Convert again' });
    again.addEventListener('click', () => convertArabizi(true));
    hint.append(again);
  }
}

function wireArabizi() {
  $('text').addEventListener('input', () => {
    clearTimeout(arabizi.timer);
    arabizi.timer = setTimeout(() => convertArabizi(), 250);
  });
  $('arabic').addEventListener('input', () => { arabizi.edited = true; });
  $('arabizi-force').addEventListener('click', () => { arabizi.forced = true; convertArabizi(true); });
}

/* ---------- Reference voice ---------- */

async function setReference(blob, name) {
  try {
    const { blob: wav, buffer } = await toWav(blob);
    if (buffer.duration < 1) throw new Error('That recording is too short. Use at least one second of speech.');
    state.reference = { blob: wav, buffer, name };
    $('reference').dataset.filled = 'true';
    $('ref-name').textContent = name;
    $('ref-length').textContent = `${buffer.duration.toFixed(1)} s` + (buffer.duration > 12 ? ' · long, consider trimming' : '');
    $('ref-audio').src = URL.createObjectURL(wav);
    requestAnimationFrame(() => drawWave($('ref-wave'), buffer));
  } catch (error) {
    toast(error.message.includes('decode') || error.name === 'EncodingError'
      ? 'That file could not be read as audio. Try a WAV or MP3 file.' : error.message);
  }
}

function clearReference() {
  state.reference = null;
  $('reference').dataset.filled = 'false';
  $('ref-audio').pause();
  if ($('ref-audio').src) URL.revokeObjectURL($('ref-audio').src);
  $('ref-audio').removeAttribute('src');
  $('file').value = '';
}

async function toggleRecording() {
  const button = $('record');
  if (state.recorder) return state.recorder.stop();
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch { return toast('Microphone access was blocked. Allow it in the browser to record.'); }
  const chunks = [];
  const recorder = new MediaRecorder(stream);
  state.recorder = recorder;
  const started = Date.now();
  button.classList.add('recording');
  const label = button.lastElementChild;
  const tick = setInterval(() => {
    const seconds = (Date.now() - started) / 1000;
    label.textContent = `Stop · ${seconds.toFixed(0)}s`;
    if (seconds >= MAX_RECORD_SECONDS) recorder.stop();
  }, 200);
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  recorder.onstop = async () => {
    clearInterval(tick);
    stream.getTracks().forEach((t) => t.stop());
    state.recorder = null;
    button.classList.remove('recording');
    label.textContent = 'Record';
    if (chunks.length) await setReference(new Blob(chunks, { type: recorder.mimeType }), 'Microphone recording');
  };
  recorder.start();
}

async function usePreset() {
  const preset = state.info.presets[0];
  const response = await fetch(`/api/presets/${preset.id}`);
  if (!response.ok) return toast('The Lumio voice could not be loaded.');
  await setReference(await response.blob(), preset.name);
  $('transcript').value = preset.transcript;
}

async function transcribe() {
  if (!state.reference) return toast('Add a reference recording first.');
  const button = $('transcribe');
  button.disabled = true; button.textContent = 'Listening…';
  try {
    const body = new FormData();
    body.append('reference', state.reference.blob, 'reference.wav');
    const response = await fetch('/api/transcribe', { method: 'POST', body });
    if (!response.ok) throw new Error(await readError(response));
    $('transcript').value = (await response.json()).transcript;
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; button.textContent = 'Transcribe it for me'; }
}

/* ---------- Generation ---------- */

async function generate(event) {
  event?.preventDefault();
  if (state.busy) return;
  const typed = $('text').value.trim();
  const text = arabiziActive() ? $('arabic').value.trim() : typed;
  if (!text) return toast('Write something for the voice to say.');
  const isClone = state.mode === 'clone' || (state.mode === 'pi5' && !!state.reference);
  if (state.mode === 'clone' && !state.reference) return toast('Add a reference voice: upload a file, record, or use the Lumio voice.');
  const language = $('language').value.trim() || 'Auto';
  if (state.info && language !== 'Auto' && !state.info.languages.includes(language)) {
    return toast(`"${language}" is not in the language list. Pick one from the suggestions.`);
  }
  const batch = Math.max(1, Math.min(5, parseInt($('batch').value) || 1));

  // Build shared fields; reference blob is appended per-request below.
  const fields = {
    mode: state.mode === 'pi5' ? (isClone ? 'clone' : 'design') : state.mode, text, language,
    steps: $('steps').value, guidance: $('guidance').value,
    speed: $('speed').value, duration: $('duration').value,
    denoise: $('denoise').checked, preprocess: $('preprocess').checked,
    postprocess: $('postprocess').checked,
    normalize_text: $('normalize_text').checked,
    t_shift: $('t_shift').value, layer_penalty: $('layer_penalty').value,
    pos_temp: $('pos_temp').value, class_temp: $('class_temp').value,
    chunk_duration: $('chunk_duration').value,
  };
  if (isClone) {
    fields.transcript = $('transcript').value.trim();
    fields.instruct = $('instruct').value.trim();
  } else {
    Object.assign(fields, state.traits);
  }

  setBusy(true);
  for (let i = 1; i <= batch; i++) {
    const body = new FormData();
    for (const [key, value] of Object.entries(fields)) body.append(key, String(value ?? ''));
    if (isClone && state.reference) body.append('reference', state.reference.blob, 'reference.wav');

    const started = performance.now();
    const tick = setInterval(() => {
      const elapsed = ((performance.now() - started) / 1000).toFixed(0);
      $('generate').querySelector('.go-label').textContent =
        batch > 1 ? `Take ${i}/${batch}\u2026 ${elapsed}s` : `Generating\u2026 ${elapsed}s`;
    }, 250);
    try {
      const response = await fetch('/api/generate', { method: 'POST', body });
      if (!response.ok) throw new Error(await readError(response));
      const blob = await response.blob();
      const transcript = decodeURIComponent(response.headers.get('X-Transcript') || '');
      if (state.mode === 'clone' && transcript && !$('transcript').value.trim()) {
        $('transcript').value = transcript;
        toast('Transcribed the reference automatically. Check it for the closest match.', 'info');
      }
      addTake({
        blob, text, language, mode: state.mode, source: text !== typed ? typed : '',
        seconds: Number(response.headers.get('X-Audio-Seconds')),
        render: Number(response.headers.get('X-Render-Seconds')),
        voice: isClone ? state.reference.name : decodeURIComponent(response.headers.get('X-Instruct') || '') || "Model's choice",
        buffer: await context().decodeAudioData(await blob.arrayBuffer()),
      }, i === batch /* autoplay only the last take */);
    } catch (error) {
      toast(error.message || 'Generation failed.');
      break;
    } finally {
      clearInterval(tick);
    }
  }
  setBusy(false);
}

function setBusy(busy) {
  state.busy = busy;
  $('generate').disabled = busy;
  $('generate').classList.toggle('busy', busy);
  $('player').classList.toggle('working', busy);
  $('batch').disabled = busy;
  if (!busy) $('generate').querySelector('.go-label').textContent = 'Generate voice';
}

/* ---------- Takes & playback ---------- */

function addTake(take, autoplay = true) {
  take.id = (state.takes[0]?.id || 0) + 1;
  take.url = URL.createObjectURL(take.blob);
  state.takes.unshift(take);
  for (const old of state.takes.splice(12)) URL.revokeObjectURL(old.url);
  showTake(take, autoplay);
}

function showTake(take, autoplay = false) {
  state.current = take;
  const audio = $('audio');
  audio.pause();
  audio.src = take.url;
  $('player').dataset.empty = 'false';
  $('take-mode').textContent = take.mode === 'clone' ? `Cloned · ${take.voice}` : `Designed · ${take.voice}`;
  $('take-title').textContent = `Take ${take.id}`;
  $('take-text').textContent = take.text;
  $('take-source').hidden = !take.source;
  $('take-source').replaceChildren(Object.assign(document.createElement('b'), { textContent: 'Typed as Arabizi: ' }), take.source || '');
  $('take-lang').textContent = take.language === 'Auto' ? 'Auto language' : take.language;
  $('take-render').textContent = `Made in ${take.render.toFixed(1)}s`;
  $('download').href = take.url;
  $('download').download = `lumio-take-${take.id}.wav`;
  $('time').textContent = `0:00 / ${clock(take.seconds)}`;
  requestAnimationFrame(() => drawWave($('wave'), take.buffer));
  renderHistory();
  if (autoplay) audio.play().catch(() => {});
}

function renderHistory() {
  const list = $('history');
  list.replaceChildren();
  if (!state.takes.length) return list.append(Object.assign(document.createElement('li'), { className: 'none', textContent: 'Nothing yet.' }));
  for (const take of state.takes) {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('aria-current', String(take === state.current));
    const num = Object.assign(document.createElement('span'), { className: 'num', textContent: take.id });
    const what = Object.assign(document.createElement('span'), { className: 'what' });
    what.append(Object.assign(document.createElement('b'), { textContent: take.text, dir: 'auto' }),
                Object.assign(document.createElement('span'), { textContent: `${take.mode === 'clone' ? 'Cloned' : 'Designed'} · ${take.language}` }));
    const len = Object.assign(document.createElement('span'), { className: 'len', textContent: clock(take.seconds) });
    button.append(num, what, len);
    button.addEventListener('click', () => showTake(take, true));
    item.append(button);
    list.append(item);
  }
}

function wirePlayer() {
  const audio = $('audio');
  $('play').addEventListener('click', () => (audio.paused ? audio.play() : audio.pause()));
  audio.addEventListener('play', () => $('play').classList.add('playing'));
  audio.addEventListener('pause', () => $('play').classList.remove('playing'));
  audio.addEventListener('ended', () => $('play').classList.remove('playing'));
  const frame = () => {
    if (state.current) {
      const duration = audio.duration || state.current.seconds;
      drawWave($('wave'), state.current.buffer, duration ? audio.currentTime / duration : 0);
      $('time').textContent = `${clock(audio.currentTime)} / ${clock(duration)}`;
    }
    if (!audio.paused) requestAnimationFrame(frame);
  };
  audio.addEventListener('play', () => requestAnimationFrame(frame));
  audio.addEventListener('seeked', frame);
  audio.addEventListener('ended', frame);
  $('wave').addEventListener('click', (e) => {
    if (!audio.duration) return;
    const box = e.currentTarget.getBoundingClientRect();
    audio.currentTime = ((e.clientX - box.left) / box.width) * audio.duration;
  });

  const ref = $('ref-audio');
  $('ref-play').addEventListener('click', () => (ref.paused ? ref.play() : ref.pause()));
  const refFrame = () => {
    if (state.reference) drawWave($('ref-wave'), state.reference.buffer, ref.duration ? ref.currentTime / ref.duration : 0);
    if (!ref.paused) requestAnimationFrame(refFrame);
  };
  ref.addEventListener('play', () => requestAnimationFrame(refFrame));
  ref.addEventListener('ended', refFrame);
}

/* ---------- Controls ---------- */

function wireControls() {
  document.querySelectorAll('.mode').forEach((b) => b.addEventListener('click', () => setMode(b.dataset.mode)));
  const count = () => { $('count').textContent = `${$('text').value.length} / 2000`; };
  $('text').addEventListener('input', count); count();
  $('language').addEventListener('input', syncLanguage);

  const sliders = { speed: (v) => `${Number(v).toFixed(2)}×`, steps: (v) => v, guidance: (v) => Number(v).toFixed(1) };
  for (const [id, format] of Object.entries(sliders)) {
    const input = $(id);
    const update = () => {
      $(`${id}-out`).textContent = format(input.value);
      input.style.setProperty('--fill', `${((input.value - input.min) / (input.max - input.min)) * 100}%`);
    };
    input.addEventListener('input', update); update();
  }

  const drop = $('drop');
  $('file').addEventListener('change', (e) => e.target.files[0] && setReference(e.target.files[0], e.target.files[0].name));
  drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', (e) => {
    e.preventDefault(); drop.classList.remove('over');
    const file = e.dataTransfer.files[0];
    if (file) setReference(file, file.name);
  });
  $('record').addEventListener('click', toggleRecording);
  $('preset').addEventListener('click', usePreset);
  $('ref-clear').addEventListener('click', clearReference);
  $('transcribe').addEventListener('click', transcribe);
  $('composer').addEventListener('submit', generate);
  document.addEventListener('keydown', (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') generate(e); });

  // Lebanese quality preset
  $('lebanese-preset').addEventListener('click', () => {
    const PRESET = { steps: 48, guidance: 2.5, speed: 1.0, t_shift: 0.05,
      layer_penalty: 6.0, pos_temp: 3.0, class_temp: 0.0, chunk_duration: 12 };
    for (const [id, val] of Object.entries(PRESET)) {
      const el = $(id);
      if (el) { el.value = val; el.dispatchEvent(new Event('input')); }
    }
    $('denoise').checked = true;
    $('preprocess').checked = true;
    $('postprocess').checked = true;
    $('normalize_text').checked = false;
    toast('Lebanese quality preset applied \u2014 steps 48, guidance 2.5, rhythm 3.0.', 'info');
  });

  // Pi 5 listeners
  $('apply-pi5-profile')?.addEventListener('click', () => applyPi5Tuning(true));
  $('copy-pi5-cmd')?.addEventListener('click', async () => {
    const cmd = 'OMP_NUM_THREADS=4 .venv/bin/python studio/server.py --device cpu --port 7860';
    try {
      await navigator.clipboard.writeText(cmd);
      toast('Copied Pi 5 launch command to clipboard!', 'info');
    } catch {
      toast('Command: ' + cmd, 'info');
    }
  });

  const optA = $('opt-standalone');
  const optB = $('opt-bridge');
  optA?.addEventListener('click', () => {
    optA.classList.add('active');
    optB.classList.remove('active');
    applyPi5Tuning(true);
  });
  optB?.addEventListener('click', () => {
    optB.classList.add('active');
    optA.classList.remove('active');
    toast('Option B uses PC GPU while Pi 5 handles microphone/HA!', 'info');
  });

  let resize;
  window.addEventListener('resize', () => {
    clearTimeout(resize);
    resize = setTimeout(() => {
      if (state.current) drawWave($('wave'), state.current.buffer);
      if (state.reference) drawWave($('ref-wave'), state.reference.buffer);
    }, 120);
  });
}

wireControls();
wireArabizi();
wirePlayer();
buildQuickLanguages();
setMode('clone');
loadInfo();
