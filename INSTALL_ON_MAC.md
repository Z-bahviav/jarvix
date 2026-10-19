# Install Jarvis on your Mac

Jarvis does **not** appear on your Mac by itself. Clone it once, then run setup.

## Available now — Cursor git (pushed)

On your Mac (Terminal):

```bash
mkdir -p ~/Desktop
git clone https://origin.cursor.com/git/getwellnetwork/tmp-916c946cd0107a1d.git ~/Desktop/Jarvis
cd ~/Desktop/Jarvis
```

Use Cursor/git login if prompted. You can use any folder; `~/Desktop/Jarvis` matches this project name on the cloud VM.

## Your GitHub — after you push

1. Create empty repo: https://github.com/new → **Z-bahviav/Jarvis**
2. Push from a machine that has this code: `git push -u origin main`
3. On Mac: `git clone https://github.com/Z-bahviav/Jarvis.git ~/Jarvis`

See `PUSH_TO_GITHUB.md`.

## Setup

```bash
cd ~/Jarvis
./scripts/setup.sh
source .venv/bin/activate
pip install -e .
curl https://cursor.com/install -fsS | bash
jarvis doctor
nano .env   # JARVIS_GEMINI_API_KEY=
./scripts/go.sh
```
