#!/bin/bash
# FML · Fake My Location installer (Mac only)
#   curl -fsSL https://raw.githubusercontent.com/lukesikora/fake-my-location/main/install.sh | bash
# Running it again updates FML and keeps your saved places.
set -e

REPO="lukesikora/fake-my-location"
DIR="$HOME/FML"
LAUNCHER="$HOME/Desktop/FML.command"

say()  { printf "\n\033[1;35m%s\033[0m\n" "$1"; }
fail() { printf "\n\033[1;31m%s\033[0m\n\n" "$1"; exit 1; }

printf "\n\033[1;35m  FML · Fake My Location\033[0m\n  Created by Luke Sikora\n"

[ "$(uname)" = "Darwin" ] || fail "FML only works on a Mac."

# 1. uv: installs Python and FML's parts without needing admin rights
UV="$(command -v uv || true)"
[ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ] && UV="$HOME/.local/bin/uv"
if [ -z "$UV" ]; then
  say "Step 1 of 4: Installing Python tools…"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null 2>&1 \
    || fail "Couldn't download Python tools. Check your internet connection and try again."
  UV="$HOME/.local/bin/uv"
else
  say "Step 1 of 4: Python tools already installed."
fi

# 2. Download FML (no git needed). Your saved places in data/ are kept.
say "Step 2 of 4: Downloading FML…"
TMP="$(mktemp -d)"
curl -fsSL "https://github.com/$REPO/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP" \
  || fail "Couldn't download FML. Check your internet connection and try again."
mkdir -p "$DIR"
rsync -a --delete --exclude data --exclude .venv "$TMP"/*/ "$DIR"/
rm -rf "$TMP"
chmod +x "$DIR/start.sh"

# 3. Python + parts
say "Step 3 of 4: Installing (this can take a minute the first time)…"
if [ ! -x "$DIR/.venv/bin/python" ]; then
  "$UV" venv --quiet --python 3.12 "$DIR/.venv" || fail "Couldn't set up Python. Try running the install command again."
fi
"$UV" pip install --quiet --python "$DIR/.venv/bin/python" -r "$DIR/requirements.txt" \
  || fail "Couldn't install FML's parts. Check your internet connection and try again."

# 4. Desktop shortcut
say "Step 4 of 4: Adding FML to your Desktop…"
cat > "$LAUNCHER" <<EOF
#!/bin/bash
exec "$DIR/start.sh"
EOF
chmod +x "$LAUNCHER"

printf "\n\033[1;32m  ✓ FML is installed!\033[0m\n\n"
printf "  From now on, double-click \033[1mFML\033[0m on your Desktop to open it.\n"
printf "  Opening it for you now…\n\n"
open "$LAUNCHER"
