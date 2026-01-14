#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Homebrew check
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found."
  echo "Install it with:"
  echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  exit 1
fi

# ffmpeg check/install
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Installing ffmpeg..."
  brew install ffmpeg
fi

# venv
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt

echo "Setup complete."
echo "Next: ./scripts/run.sh /path/to/Recordings.zip"
