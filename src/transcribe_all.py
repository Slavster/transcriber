#!/usr/bin/env python3
import sys
import re
import os
import json
import subprocess
from functools import lru_cache
from pathlib import Path
from datetime import datetime, timezone
from faster_whisper import WhisperModel

AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".mp4", ".webm", ".mkv", ".caf"}

DT_RE = re.compile(r"^(\d{8}) (\d{6})")
SEQ_RE = re.compile(r"^(.*?)(?: (\d+))?$")

# Best guess at the local timezone for interpreting filename-based timestamps.
_LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc

def parse_dt_from_stem(stem: str):
    m = DT_RE.match(stem)
    if not m:
        return None
    return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")


def parse_name_sequence(stem: str) -> tuple[str, int]:
    """
    Split a filename stem like 'Ho Xuan Huong 3' into:
      ('Ho Xuan Huong', 3)
    and a stem like 'Ho Xuan Huong' into:
      ('Ho Xuan Huong', 0)

    This lets us order related files in a natural conversational sequence,
    even when their timestamps are identical to-the-second (e.g., after
    Airdrop or batch export).
    """
    m = SEQ_RE.match(stem)
    if not m:
        return stem, 0
    base = (m.group(1) or "").strip()
    num_str = m.group(2)
    try:
        idx = int(num_str) if num_str is not None else 0
    except ValueError:
        idx = 0
    return base, idx

def _parse_media_dt(s: str):
    """
    Parse common ffprobe datetime tag formats like:
      - 2026-01-13T13:10:24Z
      - 2026-01-13T13:10:24.000000Z
      - 2026-01-13 13:10:24
    Returns an aware datetime in UTC when possible.
    """
    s = (s or "").strip()
    if not s:
        return None
    # ISO 8601 (most common from ffprobe)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    # Fallback: space-separated
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue
    return None

@lru_cache(maxsize=None)
def _media_created_dt_cached(path_str: str):
    """
    Extract creation timestamp from the audio/container/stream metadata via ffprobe
    for the given path string. Returns an aware datetime in UTC if available,
    else None.
    """
    try:
        cp = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                # Ask for both container-level and stream-level tags; Voice Memos
                # sometimes stores creation info on the stream.
                "-show_entries",
                "format_tags:stream_tags",
                path_str,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if cp.returncode != 0:
            return None
        data = json.loads(cp.stdout or "{}")
        tag_dicts = []
        fmt = data.get("format") or {}
        if isinstance(fmt, dict):
            tag_dicts.append(fmt.get("tags") or {})
        # Also inspect each stream's tags – these often carry per-recording timestamps.
        for stream in data.get("streams") or []:
            if isinstance(stream, dict):
                tag_dicts.append(stream.get("tags") or {})

        # Common keys across containers; Apple / Voice Memos often use quicktime creationdate.
        for tags in tag_dicts:
            for k in ("creation_time", "com.apple.quicktime.creationdate", "date"):
                v = tags.get(k)
                dt = _parse_media_dt(v) if isinstance(v, str) else None
                if dt is not None:
                    return dt
    except Exception:
        return None
    return None


def media_created_dt(p: Path):
    """
    Cached wrapper around _media_created_dt_cached so ffprobe is only run
    once per file path.
    """
    return _media_created_dt_cached(str(p))

def iter_audio_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith("._"):
            continue
        if p.suffix.lower() in AUDIO_EXTS:
            yield p

def sort_key(p: Path):
    # Prefer true media creation time (from metadata), then filename dt, then filesystem mtime.
    dt_media = media_created_dt(p)
    if dt_media is not None:
        priority = 0
        dt = dt_media
    else:
        dt_name = parse_dt_from_stem(p.stem)
        if dt_name is not None:
            # Treat as local time: attach the local tzinfo so display stays at
            # the clock time implied by the filename.
            priority = 1
            dt = dt_name.replace(tzinfo=_LOCAL_TZ)
        else:
            priority = 2
            dt = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)

    base_name, seq_idx = parse_name_sequence(p.stem)
    # Order by (source of time, timestamp, conversational base name, sequence index, full filename)
    return (priority, dt, base_name, seq_idx, p.name)

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
    # For display, we keep a per-second counter so files that truly share the
    # same wall-clock second get a stable suffix like :2, :3, etc.
    counts_by_second: dict[datetime, int] = {}
    with combined_path.open("w", encoding="utf-8") as allf:
        for p in files:
            # Transcribe: auto language detection
            segments, info = model.transcribe(str(p), beam_size=5)
            text = "".join(seg.text for seg in segments).strip()

            per_file = transcripts_dir / f"{p.stem}.txt"
            per_file.write_text(text + "\n", encoding="utf-8")

            # Header uses media creation time if available, else filename dt, else file mtime
            dt = media_created_dt(p)
            if dt is None:
                dt = parse_dt_from_stem(p.stem)
                if dt is not None:
                    # Treat filename timestamps as local time.
                    dt = dt.replace(tzinfo=_LOCAL_TZ)
            if dt is None:
                dt = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)

            # Localized time for display plus a tie-break suffix if multiple files
            # share the exact same second.
            dt_local = dt.astimezone()
            key = dt_local.replace(microsecond=0)
            count = counts_by_second.get(key, 0) + 1
            counts_by_second[key] = count

            ts_str = dt_local.strftime("%Y-%m-%d %H:%M:%S")
            if count > 1:
                ts_str = f"{ts_str}:{count}"

            allf.write(
                f"\n===== {ts_str} | {p.name} | lang={info.language} =====\n"
            )
            allf.write(text + "\n")

    print(f"Files transcribed: {len(files)}")
    print(f"Per-file transcripts: {transcripts_dir}")
    print(f"Combined transcript: {combined_path}")

if __name__ == "__main__":
    main()