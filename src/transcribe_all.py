#!/usr/bin/env python3
import sys
import re
import os
from pathlib import Path
from datetime import datetime
from faster_whisper import WhisperModel

AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".mp4", ".webm", ".mkv", ".caf"}

DT_RE = re.compile(r"^(\d{8}) (\d{6})")

def parse_dt_from_stem(stem: str):
    m = DT_RE.match(stem)
    if not m:
        return None
    return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")

def iter_audio_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith("._"):
            continue
        if p.suffix.lower() in AUDIO_EXTS:
            yield p

def sort_key(p: Path):
    dt = parse_dt_from_stem(p.stem)
    if dt is not None:
        return (0, dt, p.name)
    # fallback: mtime
    return (1, datetime.fromtimestamp(p.stat().st_mtime), p.name)

def main():
    if len(sys.argv) < 3:
        print("Usage: transcribe_all.py <unzipped_root_dir> <out_dir>", file=sys.stderr)
        sys.exit(1)

    in_root = Path(sys.argv[1]).expanduser().resolve()
    out_root = Path(sys.argv[2]).expanduser().resolve()

    if not in_root.exists():
        print(f"Input folder not found: {in_root}", file=sys.stderr)
        sys.exit(1)

    transcripts_dir = out_root / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    out_root.mkdir(parents=True, exist_ok=True)

    files = sorted(list(iter_audio_files(in_root)), key=sort_key)

    # CPU-friendly, with configurable model size
    model_name = os.getenv("WHISPER_MODEL", "small")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")

    combined_path = out_root / "ALL_TRANSCRIPTS.txt"
    with combined_path.open("w", encoding="utf-8") as allf:
        for p in files:
            # Transcribe: auto language detection
            segments, info = model.transcribe(str(p), beam_size=5)
            text = "".join(seg.text for seg in segments).strip()

            per_file = transcripts_dir / f"{p.stem}.txt"
            per_file.write_text(text + "\n", encoding="utf-8")

            # Header uses parsed dt if available, else file mtime
            dt = parse_dt_from_stem(p.stem)
            if dt is None:
                dt = datetime.fromtimestamp(p.stat().st_mtime)

            allf.write(f"\n===== {dt.strftime('%Y-%m-%d %H:%M:%S')} | {p.name} | lang={info.language} =====\n")
            allf.write(text + "\n")

    print(f"Files transcribed: {len(files)}")
    print(f"Per-file transcripts: {transcripts_dir}")
    print(f"Combined transcript: {combined_path}")

if __name__ == "__main__":
    main()