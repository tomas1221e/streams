# Streams Manager V3

This version is based on the current `tomas1221e/streams` structure and keeps the same Flask + SQLite + FFmpeg approach while adding:

- Quick Stream Key change from the main dashboard.
- Output creation with the previous output's settings.
- Separate "same settings" and "new settings" output buttons.
- Reduced output form: common settings are selects instead of many free-text fields.
- Sticky modal header so the X button remains visible while scrolling.
- Faster dashboard refresh using one `/api/state` request.
- Faster visual feedback when starting/restarting outputs.
- Optional video enhancement filters:
  - Sharpen
  - Denoise
  - Deblock
  - Brightness
  - Contrast
  - Saturation
  - Gamma
  - Scaling
- Quality presets: Balanced, Football, Clean, Sharp, High Quality, Custom.
- Existing SQLite databases are migrated automatically with new optional columns.

## Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

FFmpeg and ffprobe must be installed and available in PATH.

## Important

`COPY` mode intentionally does not apply video filters. Filters require video processing/re-encoding.

If you already have `data/streams.db`, keep it. The application adds the new columns automatically.

Open:

http://SERVER_IP:5000
