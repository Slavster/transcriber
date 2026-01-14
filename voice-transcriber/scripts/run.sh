#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ $# -lt 1 ]; then
  echo "Usage: ./scripts/run.sh /path/to/Recordings.zip"
  exit 1
fi

ZIP_PATH="$1"
if [ ! -f "$ZIP_PATH" ]; then
  echo "Zip not found: $ZIP_PATH"
  exit 1
fi

mkdir -p work
mkdir -p out

# Fresh work dir each run
RUN_DIR="work/run_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"
unzip -q "$ZIP_PATH" -d "$RUN_DIR"

source .venv/bin/activate
python src/transcribe_all.py "$RUN_DIR" "out"

echo "Done."
echo "Per-file transcripts: out/transcripts/"
echo "Combined transcript: out/ALL_TRANSCRIPTS.txt"
