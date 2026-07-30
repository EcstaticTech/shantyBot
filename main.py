import asyncio
import logging
import sys
from pathlib import Path
import yaml
import uvicorn
import disnake

from core.library import LocalLibrary
from core.player import ShantyPlayer
from core.youtube import YouTubeIngestor
from core.bot import ShantyBot, setup_bot_commands
from core.views import MusicControlView
from web.server import create_web_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shantyBot")

def load_config():
    config_path = Path("config.yaml")
    if not config_path.exists():
        logger.error("config.yaml not found! Copy config.example.yaml to config.yaml and configure settings.")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def ensure_directories(config: dict):
    """Ensures required media and cache directories exist on startup."""
    paths = config.get("paths", {})
    dirs_to_create = [
        paths.get("media_directory", "./media/shanties"),
        paths.get("raid_directory", "./media/raid_sounds"),
        paths.get("ambient_directory", "./media/ambient"),
        paths.get("youtube_cache_directory", "./media/cache"),
    ]
    for d in dirs_to_create:
        Path(d).resolve().mkdir(parents=True, exist_ok=True)

async def main():
    config = load_config()
    ensure_directories(config)

    # Initialize Security Library, YouTube Ingestor, and Player Engine
    paths = config.get("paths", {})
    bot_cfg = config.get("bot", {})
    
    library = LocalLibrary(paths.get("media_directory", "./media/shanties"))
    youtube = YouTubeIngestor(
        cache_dir=paths.get("youtube_cache_directory", "./media/cache"),
        allowed_playlist_ids=bot_cfg.get("allowed_playlist_ids", [])
    )
    
    intents = disnake.Intents.default()
    intents.voice_states = True
    intents.guilds = True

    bot = ShantyBot(
        player=None,
        library=library,
        youtube=youtube,
        raid_path=paths.get("raid_directory", "./media/raid_sounds"),
        command_prefix=bot_cfg.get("command_prefix", "/shanty"),
        intents=intents
    )

    player = ShantyPlayer(
        bot,
        idle_timeout=bot_cfg.get("idle_disconnect_seconds", 180),
        ambient_dir=paths.get("ambient_directory", "./media/ambient")
    )
    bot.player = player
    setup_bot_commands(bot)

    # Add persistent UI view listener across bot reboots
    bot.add_view(MusicControlView(player))

    # Start FastAPI Server inside same event loop
    app = create_web_app(player)
    web_config = uvicorn.Config(
        app=app, 
        host=config["web"]["host"], 
        port=config["web"]["port"], 
        log_level="warning"
    )
    server = uvicorn.Server(web_config)
    
    asyncio.create_task(server.serve())
    await bot.start(bot_cfg["token"])

if __name__ == "__main__":
    asyncio.run(main())
