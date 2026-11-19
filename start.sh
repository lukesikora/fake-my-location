#!/bin/bash
# Starts FML · Fake My Location. Keep this window open while you're using it.
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
  if [ ! -x "$UV" ]; then
    echo "FML isn't fully installed. Paste the install command from the GitHub page into Terminal again."
    exit 1
  fi
  "$UV" venv --quiet --python 3.12 .venv
  "$UV" pip install --quiet --python .venv/bin/python -r requirements.txt
fi

clear
exec .venv/bin/python server.py --open
