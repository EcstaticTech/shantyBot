# shantyBot

A secure, zero-latency local music bot and web status server running inside a single Python asyncio event loop.

## Features
- **Mutagen Tag Metadata Extraction**: Automatically parses ID3, Vorbis, and MP4 tags (`title`, `artist`) with filename fallbacks.
- **FFmpeg Real-Time Ambient Audio Layering**: `/shanty tavern <query>` layers loopable tavern ambience under playing tracks using FFmpeg `amix`.
- **YouTube Ingestion & Cache Guard**: Non-blocking `yt-dlp` download engine with domain allowlisting, playlist validation, and automated LRU cache purging.
- **Interactive Discord UI**: Persistent Discord buttons (Pause/Resume, Skip, Raid Party) attached to Now Playing cards.
- **FastAPI Tavern Web Status Server**: Light-weight, read-only HTML and JSON endpoints bound to the `asyncio` event loop.

## Ambient Audio & Attributions
The tavern ambient layering engine defaults to loading `./media/ambient/tavern.mp3`.
- Recommended / Project Standard Sound: **[Freesound.org Sound #814284](https://freesound.org/people/Robinhood76/sounds/814284/)** by **Robinhood76** (Licensed under Creative Commons BY-NC).
- To enable default tavern ambience, save the downloaded audio file as `./media/ambient/tavern.mp3`.

## Directory Layout
```
shantyBot/
├── .gitignore
├── README.md
├── requirements.txt
├── config.example.yaml
├── main.py
├── Dockerfile
├── docker-compose.yml
├── core/
│   ├── __init__.py
│   ├── audio_source.py
│   ├── bot.py
│   ├── library.py
│   ├── player.py
│   ├── views.py
│   └── youtube.py
├── media/
│   ├── shanties/
│   ├── ambient/
│   │   └── tavern.mp3  (Default loop)
│   ├── raid_sounds/
│   └── cache/
└── web/
    ├── __init__.py
    ├── server.py
    └── templates/
        └── index.html
```

## Quick Start (Local Python)
1. Copy `config.example.yaml` to `config.yaml`:
   ```bash
   cp config.example.yaml config.yaml
   ```
2. Edit `config.yaml` to set your Discord bot token.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start shantyBot:
   ```bash
   python main.py
   ```

## Docker Container Deployment
```bash
docker-compose up -d --build
```

## Windows Service Deployment (NSSM)
To run shantyBot as a background service on Windows using Non-Sucking Service Manager (NSSM):
```cmd
nssm install shantyBot "C:\Python311\python.exe" "C:\path\to\shantyBot\main.py"
nssm set shantyBot AppDirectory "C:\path\to\shantyBot"
nssm set shantyBot AppStdout "C:\path\to\shantyBot\service.log"
nssm set shantyBot AppStderr "C:\path\to\shantyBot\service_error.log"
nssm start shantyBot
```
