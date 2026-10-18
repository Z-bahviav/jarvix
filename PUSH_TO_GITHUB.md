# Push to your GitHub (one-time)

Remote is set to: **https://github.com/Z-bahviav/Jarvis.git**

## 1. Create the repo on GitHub

1. Open https://github.com/new  
2. Owner: **Z-bahviav**  
3. Repository name: **Jarvis**  
4. **Private** or Public — your choice  
5. Do **not** add README, .gitignore, or license (we already have them)  
6. Create repository  

## 2. Push from your machine or this project folder

```bash
cd /path/to/Jarvis
git remote -v
# should show origin → https://github.com/Z-bahviav/Jarvis.git

git push -u origin main
```

Use GitHub login, PAT, or SSH:

```bash
git remote set-url origin git@github.com:Z-bahviav/Jarvis.git
git push -u origin main
```

## 3. Clone on your Mac

```bash
git clone https://github.com/Z-bahviav/Jarvis.git ~/Jarvis
cd ~/Jarvis
./scripts/setup.sh
```
