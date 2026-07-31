# shantyBot `v0.0.1-alpha`

A secure, zero-latency local music bot and live Web Status Board running inside a single Python `asyncio` event loop.

![Version](https://img.shields.io/badge/version-0.0.1--alpha-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Framework](https://img.shields.io/badge/disnake-2.9%2B-purple)
![FastAPI](https://img.shields.io/badge/fastapi-0.111%2B-green)

---

## 🏴‍☠️ Features

- **Pre-Flight Validation Engine**: Fast-fail configuration validator in `main.py` that verifies `config.yaml` and validates Discord Bot Token formatting before binding network sockets.
- **Mutagen Tag Metadata Extraction**: Automatically parses ID3, Vorbis, and MP4 tags (`title`, `artist`) with clean filename fallbacks and `display_name` formatting.
- **Persistent Ambient State Machine**: State-machine audio engine in `core/player.py` supporting persistent ambient background audio (`/shanty ambient <choice>`) overlaid with music or looped solo.
- **FFmpeg Real-Time Audio Layering**: Wraps FFmpeg subprocess pipes with `amix` filter graphs to layer ambient tracks over shanties in real time (48kHz 16-bit stereo PCM).
- **Subprocess Memory & Process Protection**: `cleanup()` flushes stderr, calls `process.kill()` and `process.wait(timeout=1)` to eliminate orphan `ffmpeg.exe` processes on Windows.
- **Strict YouTube Ingestion & Cache Guard**: Non-blocking `yt-dlp` download engine with domain allowlisting, playlist validation, and automated LRU cache purging (`purge_cache()`).
- **Interactive Discord UI**: Persistent Discord buttons (Pause/Resume, Skip) with static custom IDs attached to Now Playing cards.
- **FastAPI Web Status Board & Ship's Manifest**: Real-time Web UI (`/`) and JSON endpoint (`/api/status`) rendering live Now Playing tracks, Ambient Mode badges, Queue, and scrollable local track library.

---

## 📜 Slash Commands

| Command | Description |
| :--- | :--- |
| `/shanty play <query/url>` | Play a sea shanty from local library or an approved YouTube URL. |
| `/shanty tavern <query>` | Play a shanty overlaid with tavern ambient audio. |
| `/shanty ambient <choice>` | Toggle persistent background ambient sound (with dynamic autocomplete: *Tavern*, *Sailing*, *Off*). |
| `/shanty raid` | Instantly trigger a random raiding party audio event interrupt. |
| `/shanty list` | Ephemeral link embed directing users to the Web Status Board & Ship's Manifest. |
| `/shanty skip` | Skip the currently active track. |
| `/shanty reload` | Re-index local audio and ambient libraries into memory. |

---

## 🎵 Ambient Audio & Attributions

The tavern ambient layering engine defaults to loading `./media/ambient/tavern.mp3`.
- **Recommended / Project Standard Sound**: **[Freesound.org Sound #814284](https://freesound.org/people/Robinhood76/sounds/814284/)** by **Robinhood76** (Licensed under Creative Commons BY-NC).
- To enable default tavern ambience, place the downloaded audio file at `./media/ambient/tavern.mp3`.

---

## 📁 Directory Layout

```
shantyBot/
├── .gitignore
├── README.md
├── requirements.txt
├── config.example.yaml
├── main.py
├── Dockerfile
├── docker-compose.yml
├── test_sanity.py
├── core/
│   ├── __init__.py
│   ├── audio_source.py      # Subprocess FFmpeg amix audio source
│   ├── bot.py               # Disnake Bot client & slash commands
│   ├── config_validator.py  # Pre-flight diagnostic validator
│   ├── library.py           # Mutagen metadata indexer & RAM search
│   ├── player.py            # State-machine queue & ambient engine
│   ├── views.py             # Persistent disnake UI control buttons
│   └── youtube.py           # yt-dlp allowlist ingestion & cache guard
├── media/
│   ├── shanties/            # Local shanty audio files (.mp3, .flac, .opus, .m4a)
│   ├── ambient/             # Ambient background tracks (.mp3, .wav)
│   ├── raid_sounds/         # Sound effect clips for /shanty raid
│   └── cache/               # Automated yt-dlp Opus cache
└── web/
    ├── __init__.py
    ├── server.py            # FastAPI Web Status Board & JSON API
    └── templates/
        └── index.html       # Glassmorphism HTML status dashboard
```

---

## 🚀 Getting Started

### Prerequisites
1. **Python 3.11+** installed.
2. **FFmpeg** installed and accessible in system `PATH` (or placed as `ffmpeg.exe` in the workspace root).

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
     public_url: "http://localhost:8000"
   ```
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Run Sanity Check Suite**:
   ```bash
   python test_sanity.py
   ```
5. **Start shantyBot**:
   ```bash
   python main.py
   ```

---

## 🐳 Container Deployment (Docker)

To run shantyBot in a container with pre-packaged FFmpeg and Python 3.11-slim:

```bash
docker-compose up -d --build
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

- **Version**: `0.0.1-alpha`
- **License**: MIT
