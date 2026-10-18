# Install Jarvis on your Mac

Jarvis is **not** installed automatically on `~/Desktop/Jarvis`. You need a copy of this folder on your machine.

## Option A — Clone from your Cursor / git repo

If this project is in git (e.g. after your agent pushed it):

```bash
cd ~
git clone <YOUR_REPO_URL> Jarvis
cd Jarvis
./scripts/setup.sh
source .venv/bin/activate
```

Use any folder you like (`~/Jarvis`, `~/Projects/Jarvis`, etc.) — **not** required to be on Desktop.

## Option B — Copy from Cursor Cloud Agent

1. Open the cloud agent run that built Jarvis.
2. Use **Create repo** / download / sync if your workflow provides it.
3. Or zip the `Jarvis` folder from the agent workspace and copy to your Mac.

## After you have the folder

```bash
cd ~/Jarvis   # wherever you put it
./scripts/setup.sh
source .venv/bin/activate
pip install -e .

curl https://cursor.com/install -fsS | bash
jarvis doctor

# Edit .env — add JARVIS_GEMINI_API_KEY=
nano .env

./scripts/go.sh check
./scripts/go.sh
```

No admin and **no** `~/.zshrc` edits required (`go.sh` loads `.env` and finds the Cursor binary).
