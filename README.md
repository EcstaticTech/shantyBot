# shantyBot `v0.0.3`

A secure, zero-latency local-first music bot, multi-channel audio engine, and live Web Status Board running inside a single Python `asyncio` event loop.

![Version](https://img.shields.io/badge/version-0.0.3-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Framework](https://img.shields.io/badge/disnake-2.9%2B-purple)
![FastAPI](https://img.shields.io/badge/fastapi-0.111%2B-green)

---

## 🏴‍☠️ Features

- **Multi-Channel Pipeline Engine**: Supports isolated voice pipelines (`ChannelAudioPipeline`) across multiple voice channels (up to 2 concurrent channels) with per-channel queues, playback locks, and volume controls.
- **Pre-Flight Validation Engine**: Fast-fail configuration validator in `main.py` that verifies `config.yaml` and validates Discord Bot Token formatting before binding network sockets.
- **Mutagen Tag & Duration Extraction**: Automatically parses ID3, Vorbis, and MP4 tags (`title`, `artist`, `duration_seconds`) with clean filename fallbacks and `display_name` formatting.
- **Persistent Ambient State Machine**: State-machine audio engine in `core/player.py` supporting persistent ambient background audio (`/shanty ambient <choice>`) overlaid with music or looped solo.
- **Dynamic Ambient Indexing & Hot-Swapping**: Automatically scans `./media/ambient/` for `.mp3`, `.flac`, `.opus`, `.m4a`, and `.wav` files at runtime with dynamic autocomplete choices.
- **FFmpeg Real-Time Audio Layering & Input Seeking**: Layer ambient tracks over shanties in real time (48kHz 16-bit stereo PCM) with `-ss <seconds>` input seeking for mid-track ambient toggles without track restarts.
- **Ambient Pause Decoupling & Callback Suppression**: Pausing a shanty smoothly switches to a solo ambient background loop without stopping ambient audio. `_swapping_streams` flag guards against queue corruption during stream swaps.
- **Drift-Free Playback Progress Counter**: Real-time `mm:ss / mm:ss` progress calculations accounting for pause states, exposed via `GET /api/v1/channels/active` and `GET /api/v1/health`.
- **JIT Opus Cache & LRU Eviction Quota**: On-demand background Opus transcoding engine with configurable disk cache quotas (`max_cache_gb: 2.0` or `0` for uncapped storage).
- **Subprocess Memory & Pipe Flushing Protection**: Robust `cleanup()` flushing `stdout`/`stderr` handles before calling `proc.terminate()` to prevent return code -9 SIGKILL deadlocks and orphan `ffmpeg.exe` handles.
- **Graceful Shutdown & Orphaned Session Audit**: Intercepts `SIGINT`/`SIGTERM` container stops to execute `cleanup_all_pipelines()`, and purges orphaned gateway voice clients on startup `on_ready()`.
- **FastAPI Web Status Board & Favicon Asset Bundle**: Real-time Web UI (`/`), Active Channel selector, Favicon asset bundle (`web/static/favicons/`), and JSON API endpoints (`/api/v1/channels/active`, `/api/v1/health`).

---

## 📜 Slash Commands

| Command | Description |
| :--- | :--- |
| `/shanty play <query/url>` | Play a sea shanty from local library or an approved YouTube URL. |
| `/shanty ambient <choice>` | Toggle persistent background ambient sound (with dynamic autocomplete: *Sea Ambience*, *Tavern*, *Off*). |
| `/shanty leave` | Disconnect from your voice channel, clear queue, and free pipeline resources immediately. |
| `/shanty skip` | Skip the currently active track in your voice channel. |
| `/shanty list` | Ephemeral link embed directing users to the Web Status Board & Ship's Manifest. |
| `/shanty reload` | Re-index local audio and ambient libraries into memory. |

---

## 🎵 Ambient Audio & Attributions

The ambient audio engine dynamically indexes all valid audio files in `./media/ambient/`.
- **Recommended Default Sound**: Place ambient tracks at `./media/ambient/` (e.g. `sea.mp3`, `tavern.mp3`).
- **Attribution Example**: **[Freesound.org Sound #814284](https://freesound.org/people/Robinhood76/sounds/814284/)** by **Robinhood76** (Licensed under Creative Commons BY-NC).

---

## 📁 Directory Layout

```
shantyBot/
├── .dockerignore
├── .gitignore
├── .github/
│   └── workflows/
│       └── docker-publish.yml
├── README.md
├── pyproject.toml
├── requirements.txt
├── config.example.yaml
├── main.py
├── Dockerfile
├── docker-compose.yml
├── test_sanity.py
├── test_sprint5.py
├── core/
│   ├── __init__.py
│   ├── audio_source.py      # Subprocess FFmpeg amix & solo ambient sources
│   ├── bot.py               # Disnake Bot client, orphan audit & slash commands
│   ├── cache_index.py       # JIT Opus cache index & LRU quota manager
│   ├── config_validator.py  # Pre-flight diagnostic validator
│   ├── library.py           # Mutagen metadata indexer & RAM search
│   ├── player.py            # Multi-channel pipeline state-machine & queue
│   ├── views.py             # Persistent disnake UI control buttons
│   └── youtube.py           # yt-dlp allowlist ingestion & cache guard
├── media/
│   ├── shanties/            # Local shanty audio files (.mp3, .flac, .opus, .m4a)
│   ├── ambient/             # Hot-swappable ambient background tracks
│   ├── raid_sounds/         # Sound effect clips for raid interrupts
│   └── cache/               # Automated yt-dlp Opus cache
└── web/
    ├── __init__.py
    ├── server.py            # FastAPI Web Status Board & JSON API
    ├── static/
    │   └── favicons/        # Favicon asset bundle & site.webmanifest
    └── templates/
        └── styleguide.html
```

---

## 🚀 Getting Started

### Prerequisites
1. **Python 3.11+** installed.
2. **FFmpeg** installed and accessible in system `PATH` (or placed as `ffmpeg.exe` in workspace root).

### Installation & Execution (Local Python)

1. **Clone & Setup Configuration**:
   ```bash
   cp config.example.yaml config.yaml
   ```
2. **Configure Settings**:
   Edit `config.yaml` to insert your Discord Bot Token and set `web.public_url`:
   ```yaml
   bot:
     token: "YOUR_DISCORD_BOT_TOKEN_HERE"
   web:
     public_url: "https://your-domain.com"
   max_cache_gb: 2.0
   ```
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Run Integration Test Suite**:
   ```bash
   python test_sprint5.py
   ```
5. **Start shantyBot**:
   ```bash
   python main.py
   ```

---

## 🐳 Container Deployment (Docker)

To deploy shantyBot using the multi-architecture container published on GitHub Container Registry:

1. Create a `docker-compose.yml` file on your server:

```yaml
version: '3.8'

services:
  shantybot:
    image: ghcr.io/ecstatictech/shantybot:latest
    container_name: shantybot
    restart: unless-stopped
    volumes:
      - ./config.yaml:/app/config.yaml
      - ./media/shanties:/app/media/shanties
      - ./media/ambient:/app/media/ambient
      - ./media/cache:/app/media/cache
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
```

2. Copy `config.example.yaml` to `config.yaml` and configure your bot token.
3. Start the container:

```bash
docker-compose up -d
```

---

## ⚙️ Windows Service Deployment (NSSM)

To deploy shantyBot as a background service on Windows using Non-Sucking Service Manager (NSSM):

```cmd
nssm install shantyBot "C:\Python311\python.exe" "C:\path\to\shantyBot\main.py"
nssm set shantyBot AppDirectory "C:\path\to\shantyBot"
nssm set shantyBot AppStdout "C:\path\to\shantyBot\service.log"
nssm set shantyBot AppStderr "C:\path\to\shantyBot\service_error.log"
nssm start shantyBot
```

---

## 📄 Versioning & License

- **Version**: `0.0.3`
- **License**: Apache 2.0
