const $ = id => document.getElementById(id);
let history = [], busy = false, recorder = null, chunks = [], micStream = null, objectUrl = null, recordTimer, offline = false;
async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || `Request failed (${response.status})`);
  }
  return response;
}
const jsonPost = body => ({method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
function status(text, error = false) { $('status').textContent = text; $('status').classList.toggle('error', error); }
function setBusy(value) {
  busy = value;
  for (const id of ['send','record','voice-test','clear']) $(id).disabled = value;
  for (const button of document.querySelectorAll('[data-sample],.bubble button')) button.disabled = value;
}
function message(role, text) {
  if (!$('messages').querySelector('.bubble')) $('messages').replaceChildren();
  const div = document.createElement('div'); div.className = `bubble ${role}`;
  const label = document.createElement('span'); label.className = 'speaker'; label.textContent = role === 'user' ? 'You' : 'Lumio';
  const content = document.createElement('div'); content.dir = 'auto'; content.textContent = text;
  div.append(label, content);
  if (role === 'assistant') {
    const button = document.createElement('button'); button.className = 'subtle'; button.textContent = 'Listen again';
    button.onclick = async () => { if (busy) return; setBusy(true); try { await speak(text); } catch(e) {status(e.message,true);} finally {setBusy(false);} };
    div.append(button);
  }
  $('messages').append(div); $('messages').scrollTop = $('messages').scrollHeight;
}
async function speak(text) {
  status(offline ? 'Generating speech on your laptop… First use loads the voice model.' : 'Generating Levantine Arabic speech… The public demo may queue your request.');
  const response = await api('/api/tts', jsonPost({text}));
  if (objectUrl) URL.revokeObjectURL(objectUrl);
  objectUrl = URL.createObjectURL(await response.blob());
  $('audio').src = objectUrl;
  try { await $('audio').play(); status('Ready.'); }
  catch { status('Audio is ready. Press Play below to listen.'); }
}
async function send(text) {
  if (busy || !text.trim()) return;
  setBusy(true); status('Thinking in Lebanese Arabic…');
  message('user',text); const pending = [...history,{role:'user',content:text}];
  try {
    const answer = await (await api('/api/chat',jsonPost({messages:pending}))).json();
    history = [...pending,answer].slice(-30); message('assistant',answer.content); $('text').value = '';
    try { await speak(answer.content); } catch(e) {status(`Reply received, but speech failed: ${e.message}`,true);}
  } catch(e) {status(e.message,true);} finally {setBusy(false);}
}
async function refresh() {
  const data = await (await api('/api/status')).json();
  offline = !!data.offline;
  $('chat-model').value = data.chat_model;
  $('connection').textContent = data.groq_configured ? 'Key saved' : 'Needs Groq key';
  $('connection').classList.toggle('ready',data.groq_configured);
  $('groq-key').placeholder = data.groq_configured ? 'Saved · leave blank to retain' : 'Enter a key locally';
  $('hf-token').placeholder = data.hf_configured ? 'Saved · leave blank to retain' : 'Optional token';
  $('reference-text').value = data.reference_text;
  $('reference-status').textContent = data.reference_ready ? 'Reference saved · cloning mode' : 'No reference saved · voice design mode';
  $('lan-status').textContent = data.lan_enabled ? 'Voice bridges are listening on the home network.' : 'Local testing mode. Run start.ps1 -Lan to make voice bridges reachable from Home Assistant.';
  if (offline) {
    document.querySelector('.badge').textContent = 'Fully offline · Lebanese Arabic';
    document.querySelector('.intro p').textContent = 'Listening, thinking, and speaking run on your laptop. Type in Lebanese Arabic or Arabizi.';
    document.querySelector('#settings-form').hidden = true;
    document.querySelector('#connection').textContent = 'Offline';
    document.querySelector('#connection').classList.add('ready');
    document.querySelector('#connection').closest('section').querySelector('p').textContent = 'Local Whisper for listening, Qwen3 for replies, and OmniVoice for speech. No API key or online provider is used. First use loads the models.';
    document.querySelector('#reference-form').closest('section').querySelector('p').textContent = 'Local OmniVoice uses Levantine Arabic and your saved reference audio and transcript. Accent and pronunciation can vary.';
    document.querySelector('footer').textContent = 'Offline mode: models and inference stay on this laptop. The laptop test desk has no connected Home Assistant device tools.';
    $('lan-status').textContent = data.lan_enabled ? 'Local model bridges are listening on the home network.' : 'Local bridges only. Use start-offline.ps1 -Lan when connecting Home Assistant on a trusted network.';
  }
  return data;
}
$('chat-form').onsubmit = e => {e.preventDefault();send($('text').value);};
$('text').onkeydown = e => {if(e.key==='Enter' && !e.shiftKey){e.preventDefault();send($('text').value);}};
$('clear').onclick = () => {history=[];$('messages').replaceChildren();status('New conversation started.');};
for(const button of document.querySelectorAll('[data-sample]')) button.onclick=()=>{$('text').value=button.dataset.sample;$('text').focus();};
$('voice-test').onclick = async () => {
  if(busy)return;setBusy(true);
  try {await speak('أهلين! أنا لوميو، مساعدك بالبيت. فيك تحكي معي باللبناني. شو بدّك نعمل هلّق؟');}
  catch(e){status(e.message,true);}finally{setBusy(false);}
};
$('settings-form').onsubmit = async e => {
  e.preventDefault();
  try {await api('/api/settings',jsonPost({groq_key:$('groq-key').value,hf_token:$('hf-token').value,chat_model:$('chat-model').value}));
    $('groq-key').value='';$('hf-token').value='';await refresh();status('Settings saved on this PC.');
  }catch(e){status(e.message,true);}
};
$('check-key').onclick = async () => {
  try {
    if($('groq-key').value) {await api('/api/settings',jsonPost({groq_key:$('groq-key').value}));$('groq-key').value='';}
    const data=await(await api('/api/models')).json();$('models').replaceChildren();
    for(const model of data.models){const option=document.createElement('option');option.value=model;$('models').append(option);}
    await refresh();status(`Key accepted. ${data.models.length} models available; choose a chat-capable model.`);
  }catch(e){status(e.message,true);}
};
$('reference-form').onsubmit = async e => {
  e.preventDefault();
  try {
    const file=$('reference').files[0];
    if(file)await api('/api/reference',{method:'POST',headers:{'Content-Type':'audio/wav'},body:file});
    await api('/api/settings',jsonPost({reference_text:$('reference-text').value}));
    await refresh();status('Voice reference settings saved.');
  }catch(e){status(e.message,true);}
};
$('remove-reference').onclick = async()=>{try{await api('/api/reference',{method:'DELETE'});$('reference').value='';await refresh();status('Reference removed.');}catch(e){status(e.message,true);}};
$('copy-token').onclick = async()=>{try{const data=await(await api('/api/bridge-token')).json();await navigator.clipboard.writeText(data.token);status('Bridge API key copied. Paste it into Home Assistant’s Ollama API Key field.');}catch(e){status(e.message,true);}};
$('record').onclick = async()=>{
  if(recorder?.state==='recording'){clearTimeout(recordTimer);recorder.stop();return;}
  if(busy)return;
  try {
    if(!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)throw new Error('Microphone recording needs a browser with MediaRecorder on localhost.');
    micStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
    const mime=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(x=>MediaRecorder.isTypeSupported(x));
    recorder=new MediaRecorder(micStream,mime?{mimeType:mime}:{});chunks=[];
    recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
    recorder.onstop=async()=>{
      clearTimeout(recordTimer);micStream.getTracks().forEach(t=>t.stop());micStream=null;
      $('record').textContent='● Record';$('record').classList.remove('recording');
      setBusy(true);status('Transcribing Lebanese Arabic…');
      try {
        const blob=new Blob(chunks,{type:recorder.mimeType});
        const data=await(await api('/api/stt',{method:'POST',headers:{'Content-Type':blob.type},body:blob})).json();
        if(!data.text)throw new Error('No speech recognized. Try again.');
        $('text').value=data.text;setBusy(false);await send(data.text);
      }catch(e){status(e.message,true);}finally{setBusy(false);}
    };
    recorder.start();busy=true;$('record').textContent='■ Stop recording';$('record').classList.add('recording');
    $('send').disabled=true;$('voice-test').disabled=true;$('clear').disabled=true;
    status('Listening… Press Stop when finished. Maximum recording: thirty seconds.');
    recordTimer=setTimeout(()=>{if(recorder.state==='recording')recorder.stop();},30000);
  }catch(e){micStream?.getTracks().forEach(t=>t.stop());status(e.message,true);setBusy(false);}
};
window.addEventListener('beforeunload',()=>{micStream?.getTracks().forEach(t=>t.stop());if(objectUrl)URL.revokeObjectURL(objectUrl);});
refresh().then(data=>status(data.groq_configured?'Ready. Type a message or record your voice.':'Add a Groq key to enable conversations. You can try the voice separately now.')).catch(e=>status(e.message,true));
