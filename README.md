# Voice Transcriber

A local tool for transcribing voice recordings with automatic language detection (English/Russian).

## Prerequisites

- macOS
- Python 3
- Homebrew

## Setup

Run the setup script to install dependencies:

```bash
./scripts/setup.sh
```

This will:
- Check for Homebrew (provide instructions if missing)
- Install ffmpeg via Homebrew if needed
- Create a Python virtual environment
- Install required packages

## Usage

Run the transcription script with a zip file containing your recordings:

```bash
./scripts/run.sh ~/Desktop/Recordings.zip
```

You can optionally specify a different Whisper model size for faster (but less accurate) transcription:

```bash
WHISPER_MODEL=base ./scripts/run.sh ~/Desktop/Recordings.zip
```

Default model is `small`. Available options: `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3`.

## Outputs

- **Per-file transcripts**: `out/transcripts/<filename>.txt` - One transcript file per audio file
- **Combined transcript**: `out/ALL_TRANSCRIPTS.txt` - All transcripts combined, ordered by date (earliest → latest)

Each entry in the combined file includes:
- Date and time (parsed from filename or file modification time)
- Original filename
- Detected language (lang=en or lang=ru)

## Notes

- Raw ASR output: Transcripts are direct from the speech recognition model with no post-processing
- May include punctuation and formatting as detected by the model
- Files are sorted by date extracted from filename pattern `YYYYMMDD HHMMSS`, with fallback to file modification time

## Privacy & Git Safety

**Important**: This repository is configured to ignore personal data:

- `out/` directory contains transcripts (gitignored)
- `work/` directory contains unzipped audio files (gitignored)
- All audio/video files (`*.m4a`, `*.mp3`, `*.wav`, `*.zip`, etc.) are gitignored

Before pushing to GitHub, verify no sensitive files are tracked:

```bash
git status
git ls-files | grep -E "(out/|work/|\.(m4a|mp3|wav|zip))"
```

The above command should return no results. If it does, remove them with:

```bash
git rm -r --cached out/ work/
```
