import asyncio
import logging
import sys
from pathlib import Path
import yaml
import uvicorn
import disnake
from disnake.ext import commands

from core.config_validator import validate_preflight_config
from core.library import LocalLibrary, Track
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
        logger.error(
            "\n" + "=" * 70 + 
            "\n CONFIGURATION ERROR: 'config.yaml' NOT FOUND" +
            "\n Please copy 'config.example.yaml' to 'config.yaml' and add your settings." +
            "\n" + "=" * 70
        )
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

def setup_ambient_command(bot: ShantyBot, player: ShantyPlayer, library: LocalLibrary):
    """Registers /shanty ambient subcommand with dynamic choice autocomplete using commands.Param."""
    shanty_group = bot.get_slash_command("shanty")

    async def ambient_choice_autocomplete(inter: disnake.ApplicationCommandInteraction, user_input: str):
        ambient_dir = player.ambient_dir
        choices = ["Off"]
        if ambient_dir.exists():
            for f in sorted(ambient_dir.glob("*")):
                if f.is_file() and f.suffix.lower() in [".mp3", ".flac", ".opus", ".m4a", ".wav"]:
                    clean_name = f.stem.replace("_", " ").replace("-", " ").title()
                    choices.append(clean_name)
        filtered = [c for c in choices if user_input.lower() in c.lower()]
        return filtered[:25]

    @shanty_group.sub_command(name="ambient", description="Toggle persistent background ambient sound")
    async def shanty_ambient(
        inter: disnake.ApplicationCommandInteraction,
        choice: str = commands.Param(
            description="Select ambient audio option or Off",
            autocomplete=ambient_choice_autocomplete
        )
    ):
        await inter.response.defer()

        if choice.lower() == "off":
            await player.set_ambient_mode(None)
            return await inter.followup.send("🔇 Ambient background audio disabled.")

        track = library.search_ambient(choice)
        if not track:
            # Fallback scan directly in ambient directory
            ambient_dir = player.ambient_dir
            clean_choice = choice.strip().lower()
            if ambient_dir.exists():
                for f in ambient_dir.glob("*"):
                    if f.is_file() and f.suffix.lower() in [".mp3", ".flac", ".opus", ".m4a", ".wav"]:
                        f_clean = f.stem.replace("_", " ").replace("-", " ").title().lower()
                        if f_clean == clean_choice or f.stem.lower() == clean_choice:
                            title = f.stem.replace("_", " ").replace("-", " ").title()
                            track = Track(title=title, artist="Ambient", path=f)
                            break

        if not track:
            return await inter.followup.send(f"⚠️ Could not find ambient track: `{choice}`", ephemeral=True)

        if not inter.author.voice:
            return await inter.followup.send("Ye must be in a voice channel to set ambient mode!", ephemeral=True)

        if not player.voice_client or not player.voice_client.is_connected():
            player.voice_client = await inter.author.voice.channel.connect()

        await player.set_ambient_mode(track)
        await inter.followup.send(f"🍻 Ambient background set to: **{track.title}**")

def setup_list_command(bot: ShantyBot, config: dict):
    """Registers /shanty list subcommand to direct users to the Web Status Board / Manifest."""
    shanty_group = bot.get_slash_command("shanty")

    @shanty_group.sub_command(name="list", description="View the full ship's manifest and available shanties")
    async def shanty_list(inter: disnake.ApplicationCommandInteraction):
        status_url = config.get("web", {}).get("public_url", "http://localhost:8000")
        embed = disnake.Embed(
            title="📜 The Ship's Manifest",
            description=f"View all indexed shanties, active queue, and ambient mode settings live on the status board:\n\n👉 **[{status_url}]({status_url})**",
            color=disnake.Color.gold()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)

async def main():
    config = load_config()

    # Pre-Flight Check: Intercept placeholder or malformed tokens before initializing subsystems
    if not validate_preflight_config(config):
        sys.exit(1)

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
    setup_ambient_command(bot, player, library)
    setup_list_command(bot, config)

    # Add persistent UI view listener across bot reboots
    bot.add_view(MusicControlView(player))

    # Start FastAPI Server inside same event loop passing both player and library
    app = create_web_app(player, library)
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
