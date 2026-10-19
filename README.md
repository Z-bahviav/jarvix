# Jarvis

Conversational voice assistant for **macOS** (dev-friendly on Linux). Chat with **Google Gemini**, speak and listen with **local Whisper** STT, and **delegate coding tasks** to **Cursor Agent** in the background.

## Features (v0.1)

- Multi-turn chat (CLI `jarvis chat` or `jarvis ui`)
- NiceGUI desktop chat: text + hold-to-talk mic
- Gemini with `delegate_cursor_task` routing to async `cursor-agent` jobs
- Spoken assistant replies (pyttsx3 / macOS `say` fallback)
- Project registry (`config/projects.yaml`) with optional confirmation before Cursor runs

## Requirements

- Python **3.11 or 3.12** (not 3.13+ — `faster-whisper` / `ctranslate2` has no wheels yet)
- [Cursor Agent CLI](https://cursor.com/docs/cli) (`cursor-agent login`)
- `JARVIS_GEMINI_API_KEY` or `GEMINI_API_KEY`
- Microphone (for voice)

## Quick start

**First time** (creates `.venv`, installs deps, copies `.env.example` → `.env`):

```bash
cd ~/Desktop/Jarvis
chmod +x scripts/setup.sh
./scripts/setup.sh
source .venv/bin/activate
```

Or manually:

```bash
cd ~/Desktop/Jarvis
python3.12 -m venv .venv   # or python3.11
source .venv/bin/activate
pip install -e ".[dev,tts]"

cp .env.example .env
# Edit .env and set JARVIS_GEMINI_API_KEY (loaded automatically on startup)

# Edit config/projects.yaml with your repo paths

jarvis check
jarvis ui
```

Open `http://127.0.0.1:8765` if the browser does not open automatically.

On headless or cloud VMs, set `JARVIS_UI_SHOW=0` and use Cursor’s port preview (or SSH tunnel) to reach the UI. Override port with `JARVIS_UI_PORT` if needed.

**Voice in the UI:** press **Voice** for ChatGPT-style live conversation (live captions while you speak, auto-send when you pause). Use Chrome or Edge for best results (Web Speech API). The small mic icon is optional dictation (Whisper). For server-side capture instead, set `JARVIS_VOICE_SERVER_MIC=1`.

## Configuration

| Path | Purpose |
|------|---------|
| `config/settings.yaml` | Hotkey, STT, LLM, TTS, UI port, Cursor |
| `config/projects.yaml` | Named repos for delegation |
| `JARVIS_CONFIG_DIR` | Override config directory |

## macOS notes

- **Microphone:** System Settings → Privacy → Microphone → allow Terminal or your app.
- **Global hotkey:** not enabled by default in v0.1 (use in-app mic). Future: Accessibility permission for `pynput`.
- **Notifications / focus Cursor:** uses `osascript` on Darwin.
- **Managed Mac (root-owned `~/.zshrc`):** do not edit `.zshrc`. Use `scripts/go.sh` or set `cursor.binary: "~/.local/bin/agent"` in `config/settings.yaml`. Jarvis auto-finds `~/.local/bin/agent` when `binary` is `agent` or `cursor-agent`.

```bash
chmod +x scripts/go.sh
jarvis doctor              # finds Cursor CLI, writes config/settings.local.yaml
~/Desktop/Jarvis/scripts/go.sh check
~/Desktop/Jarvis/scripts/go.sh         # UI (loads .env, runs doctor)
```

**Cursor CLI missing?** Run the installer, then `jarvis doctor` (searches `~/.local/share/cursor-agent/...` even if `~/.local/bin` symlinks are broken).

## Verify install (check, pytest, chat, Cursor mock)

```bash
chmod +x scripts/*.sh
./scripts/run-verification.sh
```

Uses a mock `cursor-agent` in `scripts/` when the real CLI is not installed.

## Dry-run Cursor jobs

```bash
export JARVIS_CURSOR_DRY_RUN=1
jarvis chat -t "In project jarvis-test, read README. Do not modify files."
```

## License

MIT (add your preference)
