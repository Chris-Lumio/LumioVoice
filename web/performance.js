'use strict';

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
let all = [];
let filter = 'all';

function visibleRows() {
  if (filter === 'failed') return all.filter((item) => !item.ok);
  return filter === 'all' ? all : all.filter((item) => item.kind === filter);
}

function label(kind) {
  return ({ chat: 'AI reply', stt: 'Transcription', tts: 'Speech generation' }[kind] || String(kind || 'Request'));
}

function render() {
  const rows = visibleRows();
  const successful = all.filter((item) => item.ok);
  const durations = successful.map((item) => Number(item.duration_ms) || 0).filter(Boolean);
  const average = durations.length ? durations.reduce((sum, value) => sum + value, 0) / durations.length : 0;
  const fastest = durations.length ? Math.min(...durations) : 0;
  const audio = all.reduce((sum, item) => sum + (Number(item.audio_seconds) || 0), 0);

  $('total').textContent = all.length;
  $('success-rate').textContent = all.length ? `${Math.round(successful.length / all.length * 100)}% successful` : 'No requests yet';
  $('average').textContent = average ? `${average.toFixed(0)} ms` : '—';
  $('fastest').textContent = fastest ? `${fastest.toFixed(0)} ms` : '—';
  $('audio-total').textContent = audio ? `${audio.toFixed(1)} s` : '—';
  $('summary').textContent = `${rows.length} record${rows.length === 1 ? '' : 's'} shown`;
  $('rows').innerHTML = rows.map((item) => {
    const characters = item.characters ?? item.output_characters ?? '—';
    const model = item.model || (item.kind === 'tts' ? 'Voice engine' : item.kind === 'stt' ? 'Speech recognizer' : 'Chat model');
    return `<tr><td><div class="request-name">${esc(label(item.kind))}</div><div class="muted">${esc(item.kind || '')}</div></td><td>${esc(model)}</td><td><span class="status ${item.ok ? 'ok' : 'bad'}"><i class="status-dot"></i>${item.ok ? 'Success' : 'Failed'}</span></td><td><strong>${esc(item.duration_ms)} ms</strong></td><td>${esc(item.audio_seconds ? `${item.audio_seconds} s` : '—')}</td><td>${esc(characters)}</td><td>${esc(new Date(item.timestamp).toLocaleString())}</td><td>${esc(item.error || '—')}</td></tr>`;
  }).join('') || '<tr><td class="empty-cell" colspan="8">No records match this filter.</td></tr>';
}

async function load() {
  try {
    all = (await (await fetch('/api/performance', { cache: 'no-store' })).json()).items || [];
    render();
  } catch {
    $('summary').textContent = 'Unable to load records';
  }
}

document.querySelectorAll('[data-filter]').forEach((button) => button.addEventListener('click', () => {
  document.querySelectorAll('[data-filter]').forEach((item) => item.classList.remove('active'));
  button.classList.add('active');
  filter = button.dataset.filter;
  render();
}));
$('refresh').onclick = load;
$('clear').onclick = async () => {
  if (confirm('Clear performance history?')) {
    await fetch('/api/performance', { method: 'DELETE' });
    await load();
  }
};
load();
