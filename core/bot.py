import os
import random
from pathlib import Path
import disnake
from disnake.ext import commands
from core.player import PlayableItem
from core.views import MusicControlView

class ShantyBot(commands.Bot):
    def __init__(self, player, library, youtube, raid_path: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.player = player
        self.library = library
        self.youtube = youtube
        self.raid_path = Path(raid_path).resolve()

def setup_bot_commands(bot: ShantyBot):
    @bot.slash_command(name="shanty", description="Sea shanty player commands")
    async def shanty(inter: disnake.ApplicationCommandInteraction):
        pass

    async def _resolve_track(inter: disnake.ApplicationCommandInteraction, query: str):
        """Helper to resolve track from URL or local library search."""
        if query.startswith("http://") or query.startswith("https://"):
            if not bot.youtube.is_url_allowed(query):
                await inter.followup.send("Arrr! That URL is not on the captain's approved map!")
                return None
            
            track = await bot.youtube.fetch_track(query)
            if not track:
                await inter.followup.send(f"Couldn't retrieve shanty from YouTube URL.")
                return None
            return track
        else:
            track = bot.library.search(query)
            if not track:
                await inter.followup.send(f"Couldn't find '{query}' in the ship's logs.")
                return None
            return track

    @shanty.sub_command(name="play", description="Play a shanty from local library or YouTube URL")
    async def play(inter: disnake.ApplicationCommandInteraction, query: str):
        await inter.response.defer()
        
        track = await _resolve_track(inter, query)
        if not track:
            return

        bot.player.queue.append(PlayableItem(track, mode="standard"))
        view = MusicControlView(bot.player)
        await inter.followup.send(f"Added to queue: **{track.title}**", view=view)

        if not inter.author.voice:
            await inter.followup.send("Ye must be in a voice channel to summon the crew!", ephemeral=True)
            return

        if not bot.player.voice_client or not bot.player.voice_client.is_connected():
            bot.player.voice_client = await inter.author.voice.channel.connect()
            bot.player.play_next()

    @shanty.sub_command(name="tavern", description="Play a shanty overlaid with tavern ambient audio")
    async def tavern(inter: disnake.ApplicationCommandInteraction, query: str):
        await inter.response.defer()
        
        track = await _resolve_track(inter, query)
        if not track:
            return

        bot.player.queue.append(PlayableItem(track, mode="tavern"))
        
        ambient_file = bot.player.ambient_dir / "tavern.mp3"
        note = "" if ambient_file.exists() else "\n*(Note: Playing shanty without tavern ambience — ambient track missing on host)*"
        
        view = MusicControlView(bot.player)
        await inter.followup.send(f"🍻 Added to tavern queue: **{track.title}**{note}", view=view)

        if not inter.author.voice:
            await inter.followup.send("Ye must be in a voice channel to summon the crew!", ephemeral=True)
            return

        if not bot.player.voice_client or not bot.player.voice_client.is_connected():
            bot.player.voice_client = await inter.author.voice.channel.connect()
            bot.player.play_next()

    @shanty.sub_command(name="skip", description="Skip the current playing shanty")
    async def skip(inter: disnake.ApplicationCommandInteraction):
        if bot.player.voice_client and (bot.player.voice_client.is_playing() or bot.player.voice_client.is_paused()):
            bot.player.voice_client.stop()
            await inter.response.send_message("Skipped to the next track!")
        else:
            await inter.response.send_message("Nothing is currently playing.")

    @shanty.sub_command(name="raid", description="Trigger a raiding party audio event!")
    async def raid(inter: disnake.ApplicationCommandInteraction):
        if not inter.author.voice:
            await inter.response.send_message("Ye must be in a voice channel to lead a raiding party!", ephemeral=True)
            return

        await inter.response.defer()
        success = await bot.player.trigger_raid(inter.author.voice.channel)
        if success:
            await inter.followup.send("🏴‍☠️ **RAIDING PARTY!** Batten down the hatches!")
        else:
            await inter.followup.send("No raid sound files found in ship's hold!", ephemeral=True)

    @shanty.sub_command(name="reload", description="Reload the local media index")
    async def reload(inter: disnake.ApplicationCommandInteraction):
        count = bot.library.refresh_index()
        await inter.response.send_message(f"Library re-indexed! Found {count} tracks.")
