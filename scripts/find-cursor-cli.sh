#!/bin/zsh
# Find Cursor Agent CLI on macOS without admin or PATH changes.
echo "=== ~/.local/bin ==="
ls -la "$HOME/.local/bin" 2>&1 || echo "(missing)"

echo ""
echo "=== common paths ==="
for p in \
  "$HOME/.local/bin/agent" \
  "$HOME/.local/bin/cursor-agent" \
  "$HOME/.cursor/bin/agent" \
  "$HOME/.cursor/bin/cursor-agent" \
  "/Applications/Cursor.app/Contents/Resources/app/bin/cursor" \
  "/Applications/Cursor.app/Contents/MacOS/Cursor"
do
  if [[ -e "$p" ]]; then
    echo "FOUND: $p"
    ls -la "$p"
  fi
done

echo ""
echo "=== mdfind agent (Cursor) — may take a moment ==="
mdfind "kMDItemFSName == 'agent' && kMDItemContentType == 'public.unix-executable'" 2>/dev/null | head -20

echo ""
echo "=== find in home (maxdepth 5, slow) ==="
find "$HOME" -maxdepth 5 \( -name agent -o -name cursor-agent \) -type f 2>/dev/null | head -20

echo ""
echo "If nothing found, re-run: curl https://cursor.com/install -fsS | bash"
echo "Then: ls -la ~/.local/bin"
