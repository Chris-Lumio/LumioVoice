# Lumio — Lebanese Arabic API voice assistant

A small local test desk and Home Assistant protocol bridge. **No speech or AI model weights are installed.** Listening and AI replies use Groq; speaking uses the public OmniVoice Hugging Face Space. Internet is required.

## Current verification

- Local HTTP test desk works at **http://localhost:8790**.
- Wyoming discovery, PCM/WAV conversion, and audio delivery pass tests using the official Wyoming Python library and real local TCP connections.
- Ollama discovery, authentication, streaming-format responses, and device-tool message conversion pass local protocol tests.
- Live speech generation **passed on the Pi** using its free anonymous quota. A 103,724-byte WAV sample was generated. The earlier laptop attempt hit an exhausted anonymous quota; availability varies by account/IP and daily quota.
- Groq's **Free** plan was confirmed in the signed-in account. A test key named **Lumio Lebanese API test** is configured privately on the Pi and local test desk; it expires **27 November 2026**. No paid plan or payment method was enabled.
- The bridge is **installed and running** on the Lumio Office Pi at `/home/yaralumio1/lumio-voice-api`, as the `lumio-voice-api.service` systemd user service. User lingering is enabled so it can run without an open remote shell.
- Home Assistant **2026.7.2** successfully loaded both native integrations and created the listening, speaking, and conversation entities. A separate **Lumio Lebanese** Assist pipeline is saved in Arabic. Its existing preferred assistant was preserved.
- A real **Home Assistant → Wyoming → OmniVoice → Home Assistant** speech request passed, returning HTTP 200 with a 49,869-byte `audio/mpeg` sample.
- Live recognition of the generated Arabic WAV **passed** with the exact transcript `أهلين، شو بدّك نعمل هلّق؟` (0.42 seconds in that test). Groq also generated an Arabic reply (0.22 seconds in that test). These are individual API timings, not end-to-end microphone latency.
- A real Home Assistant conversation request to `conversation.lumio_lebanese_ai` **passed**, including the tightened Lebanese instructions.
- **Device control is enabled** on the Lumio conversation agent through Home Assistant's Assist API. It uses the **82 existing, currently registered entities exposed to Assist**, including lights, switches, climate, covers, scenes, and sensors. The existing exposure list was preserved.
- A live sensor query **passed**: Lumio retrieved the W400 temperature and answered in Lebanese Arabic (`26.6 °C` at test time).
- A live control query **passed**: Lumio issued `homeassistant.turn_off`, which delegated to `light.turn_off`, targeting only `light.aqara_magicpad_s1_plus_4` (Lamp 4 Aqara S1 Plus). Both service events shared the same action context, and Home Assistant reported that target as successful. The lamp was off before and after the test.
- The earlier nine regression checks passed on Windows and the Pi. The latest **13** checks pass locally, covering conversation history pruning, serialized inference, a 49-second rate-limit wait, and closing failed voice streams. Deployment of these latest fixes is pending Pi remote-shell recovery.
- The user's all-lights command reached Home Assistant (`HassTurnOn`, domain `light`); confirmation failed afterward. Groq requested a 49-second quota wait, above the old 45-second retry cap. A subsequent voice fetch timed out with HTTP 524. The command has not been replayed during diagnosis.
- A **live human microphone** has not been tested. The recognition test used generated speech, so room acoustics and recognition of the user's own Lebanese accent still need a microphone trial.

## Start on this Windows PC

From PowerShell in this folder:

```powershell
.\start.ps1
```

Leave that process running. Open http://localhost:8790 in a browser on this PC.

If PowerShell blocks script execution, run the Python executable directly without changing execution policy:

```powershell
.\.venv\Scripts\python.exe server.py
```

This project has an isolated `.venv` already installed. To recreate it on another machine with Python 3.12 or later:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## API accounts — free testing

1. Sign in to https://console.groq.com/keys and create a key named `Lumio Lebanese testing`. Keep the account on the **Free Plan**, without adding payment details or upgrading.
2. Paste that key into the local test desk, then select **Check key & available models**. The current default is `qwen/qwen3.8-27b`; model availability and free-plan access must be confirmed against the account. Choose a chat model with tool support for Home Assistant.
3. Optionally sign in to https://huggingface.co/settings/tokens and create a minimal token permitted to access the public OmniVoice Space. Anonymous speech worked from the Pi, but a free signed-in account has a larger daily quota. Enter a token under **Hugging Face access** in the desk for the host running the bridge. The hosted model may still queue, reject API requests, or become unavailable.
4. Select **Save settings**. Try **Hear a Lebanese phrase** first. Then type a question. Finally select **Record**, speak, and select **Stop recording**. The app stops recordings after thirty seconds and releases the microphone.

Tokens are stored in `.local/config.json` on this PC. This is a plain local file containing credentials; it is ignored by Git and never exposed in the public status endpoint. Do not share the `.local` directory. Blank token inputs retain saved values. Environment variables `GROQ_API_KEY` and `HF_TOKEN` can also supply credentials.

The app does not purchase compute, upgrade accounts, or retry indefinitely. A rate/quota error is shown to the user. **A key for an already paid provider account can still incur charges**: free-only billing is an account setting, not something this bridge can enforce. Keep both accounts on their free plans. No paid fallback is configured.

Device control sends Home Assistant's tool definitions and device context to Groq. On this account, two consecutive tool-calling requests exceeded the Free plan's input-token-per-minute allowance. The bridge removes redundant schema annotations (preserving required arguments, enums, bounds, and unit guidance) and repeated instructions. If Groq still reports HTTP 429 with a retry time of at most 60 seconds, it waits once and retries **only the AI inference request**. Home Assistant device actions are not replayed. Audio uploads are not retried. Longer waits or a repeated limit are surfaced as errors. The successful status/control tests each took about **thirty seconds**, primarily waiting for that free quota.

## Lebanese defaults

- Speech recognition: Arabic (`ar`), with Lebanese vocabulary in the recognition prompt.
- AI instructions: short, natural Lebanese Arabic in Arabic script; everyday words such as هلّق، بدّك، شو.
- Speech: `Levantine Arabic` in the original OmniVoice hosted model, female voice design by default.
- This hosted demo has no Lebanese-specific dialect selector. **A Lebanese accent is the target, not a guarantee.** It is not the Lahgtna fork's hosted API.
- For a more consistent Lebanese speaker, upload a clean **WAV** reference and its exact transcript. The same saved voice is used by the browser and Home Assistant. Without a reference, voice identity can vary between generations.

## Connect Home Assistant

The same running Python service supports Home Assistant's native **Wyoming Protocol** and **Ollama** integrations. No custom Home Assistant component is required by this design. An actual Home Assistant connection still needs to be tested.

The connected instance was inspected on 28 October 2026: Home Assistant **2026.7.2**, container installation without Supervisor, LAN address `192.168.0.129`, Tailscale address `100.85.142.34`. Its existing assistants were left untouched. The native Ollama integration in that exact release includes the API Key field. The working deployment is on the same Pi, avoiding the laptop's network/Tailscale limitations.

### Installed Pi connection

| Component | Installed value |
| --- | --- |
| Wyoming | `127.0.0.1:10700` |
| Ollama-compatible API | `http://127.0.0.1:11435` with bridge API key |
| Private settings desk | `http://127.0.0.1:8791` on the Pi |
| Listening entity | `stt.lumio_listening` |
| Speaking entity | `tts.lumio_speaking` |
| Conversation entity | `conversation.lumio_lebanese_ai` — Assist device access enabled |
| Assist pipeline | `Lumio Lebanese` — Arabic (`ar`), voice `lumio-lebanese` |

The Pi already uses port 8790 for another application; Lumio uses 8791 and did not modify the existing application. All Lumio ports are bound to loopback. No router rules, public tunnels, or firewall exceptions were added. The local laptop test desk at port 8790 is a **separate conversation-only instance**; it has no Home Assistant device tools. Use **Home Assistant Assist → Lumio Lebanese** for device control. Settings saved in the laptop desk do not automatically synchronize to the Pi.

Service management on the Pi:

```bash
systemctl --user status lumio-voice-api.service
systemctl --user restart lumio-voice-api.service
systemctl --user stop lumio-voice-api.service
```

To enter a Groq key directly in the Pi shell without displaying it or putting it in command history:

```bash
cd ~/lumio-voice-api
.venv/bin/python scripts/set_api_keys.py --groq
systemctl --user restart lumio-voice-api.service
```

The helper asks through a hidden prompt. Add `--hugging-face` for an optional Hugging Face token. Do not paste keys into this chat.

BrowserOS briefly used Cloudflare secure DNS to resolve `console.groq.com` during account setup. Its original **OS default / automatic** DNS setting has been restored.

### Raspberry Pi deployment preparation

`scripts/package_source.py` builds `.local/lumio-source.tar.gz` containing only application source, tests, and documentation. It excludes credentials, voice recordings, and virtual environments. After extracting it into a dedicated folder on the Pi, `bash scripts/install_linux.sh` creates an isolated environment and installs the lightweight API clients. Python **3.10+** is supported; no GPU or AI model download is needed. The Lumio Office deployment uses Python **3.13.5**; all six protocol tests passed there. `scripts/install_service.py` installs a dedicated systemd user service on desk port 8791 and checks HTTP readiness.

If Home Assistant uses host networking on that Pi, loopback bridge URLs can be used without exposing voice ports to the LAN. Otherwise check the container network before choosing a reachable private address. A Raspberry Pi Connect remote shell can be used for deployment; it is not a general network tunnel from the laptop.

### 1. Make the bridge reachable

The default binds all ports to loopback for testing. To connect Home Assistant on another machine, stop that server and restart:

```powershell
.\start.ps1 -Lan
# Or:
.\.venv\Scripts\python.exe server.py --lan
```

- Test/settings desk remains on **127.0.0.1:8790**.
- Wyoming listens on **port 10700**.
- Ollama-compatible API listens on **port 11435** and requires the bridge API key.

Use an address of this PC that the Home Assistant host can reach. A public Home Assistant dashboard URL does not establish reverse access to this PC. If they are on different networks, place the bridge beside Home Assistant or use a private VPN route. A laptop that sleeps, changes networks, or shuts down will interrupt the assistant.

If Windows Firewall blocks access, allow TCP 10700 and 11435 only from the Home Assistant host on your trusted private network. **Wyoming has no built-in authentication or encryption; do not port-forward it to the internet.** No firewall changes or public tunnels have been created by this setup.

### 2. Listening and speaking with Wyoming

In Home Assistant:

1. Go to **Settings → Devices & services → Add integration → Wyoming Protocol**.
2. Enter this PC's reachable address and port **10700**.
3. It should discover `lumio-listening` and `lumio-speaking`.

Both use the settings saved in the test desk. ASR advertises Arabic (`ar`); TTS advertises the `lumio-lebanese` voice.

### 3. AI replies with Ollama

1. Open **Connection details** in the test desk and select **Copy bridge API key**.
2. In Home Assistant, add **Ollama** with URL `http://PC-address:11435` and paste the copied bridge key into its API Key field. This is **not** the Groq key.
3. Add/configure the conversation agent using the model **`lumio-lebanese`**. It is an API alias; no local model download is needed.
4. Keep the standard Home Assistant tool instructions. The bridge additionally supplies the Lebanese language instructions.
5. For device control, choose Home Assistant control in the agent's options and expose only the entities you want it to use. Tools execute through Home Assistant's native agent; the bridge itself has no Home Assistant token or direct device access.

Current Home Assistant supports an Ollama API Key field. If your installed release lacks it or expects a different protocol version, stop and adapt/update the integration; do not remove bridge authentication merely to work around it.

### 4. Create a separate Assist pipeline

Under **Settings → Voice assistants**, add a new assistant named **Lumio Lebanese**:

| Setting | Choice |
| --- | --- |
| Language | Arabic (`ar`) |
| Conversation agent | The Ollama agent using `lumio-lebanese` |
| Speech-to-text | Lumio listening / Groq Whisper Arabic |
| Text-to-speech | Lumio speaking / `lumio-lebanese` |

Test it first using the Assist dialog or Home Assistant companion app. This does not install a wake word or room microphone. Do not replace an existing working assistant until the new pipeline passes an end-to-end test. Do not test commands against locks, alarms, or other consequential devices; start with a harmless test light or conversation-only query.

## LumioSolutions Voice Studio

A custom web studio (`studio/`) for the downloaded OmniVoice model in `.local/models/voice`, offline and on the NVIDIA GPU. It replaces the stock OmniVoice Gradio demo:

```powershell
.\start-voice-demo.cmd
```

The `.cmd` wrapper runs `start-voice-demo.ps1` even when PowerShell script execution is disabled, without changing the execution policy. Open http://127.0.0.1:7860.

- **Clone a voice:** upload or drop any audio file, record from the microphone (up to 30 seconds), or use the saved **Lumio Lebanese** reference. Leave the transcript blank, or select *Transcribe it for me*, to have the local Whisper large-v3-turbo in `.local/models/asr` fill it in; without that folder the transcript is required.
- **Design a voice:** pick gender, age, pitch, whisper style, and (English only) accent.
- **Arabizi:** typing Lebanese in Latin letters (`maraheb shou el wade3?`) is detected and converted to Arabic script (`studio/arabizi.py`) before it reaches the engine, which was not trained on Arabizi. The converted text appears in an editable box; words not in the dictionary are spelled by rules and listed so they can be checked. The digit `2` is always the hamza ء (never ق); only a written `q` becomes ق. Add common words to `WORDS` in that file; `tests/test_arabizi.py` covers it.
- **Fine-tune:** speed, exact length, quality steps, guidance, denoise, reference clean-up, and silence trimming.
- Takes show a waveform player with download and are kept in a history list until the tab is closed.

The default language is `Levantine Arabic`; all 646 OmniVoice languages are available. The studio is bound to loopback only. Stop the Lumio server first; both need the GPU. Samples are in `demo-samples/`.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check web/app.js
```

One live hosted voice check (consumes the account's ZeroGPU quota):

```powershell
.\.venv\Scripts\python.exe scripts/test_hosted_voice.py
```

The generated sample, if successful, is written to `.local/voice-test.wav`. Tests use mocked provider services unless explicitly running this live script.

## Reference documentation

- https://www.home-assistant.io/integrations/wyoming/
- https://www.home-assistant.io/integrations/ollama/
- https://github.com/OHF-Voice/wyoming
- https://huggingface.co/spaces/k2-fsa/OmniVoice
- https://console.groq.com/docs/models
- https://huggingface.co/docs/hub/spaces-zerogpu
