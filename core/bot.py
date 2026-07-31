import os
import logging
from pathlib import Path
import disnake
from disnake.ext import commands
from core.player import PlayableItem
from core.views import MusicControlView

logger = logging.getLogger("shantyBot")

class ShantyBot(commands.Bot):
    def __init__(self, player, library, youtube, raid_path: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.player = player
        self.library = library
        self.youtube = youtube
        self.raid_path = Path(raid_path).resolve()

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")

        # Task B3.3: Orphan Purge Audit - Disconnect phantom gateway sessions
        if self.voice_clients and self.player:
            for vc in list(self.voice_clients):
                try:
                    channel_id = vc.channel.id if (hasattr(vc, "channel") and vc.channel) else None
                    if not channel_id or channel_id <= 0 or channel_id not in self.player.pipelines:
                        logger.info(f"Purging orphaned voice client session in channel {channel_id}...")
                        await vc.disconnect(force=True)
                except Exception as e:
                    logger.warning(f"Error purging orphaned voice client: {e}")

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
        
        if not inter.author.voice or not inter.author.voice.channel:
            await inter.followup.send("Ye must be in a voice channel to summon the crew!", ephemeral=True)
            return

        track = await _resolve_track(inter, query)
        if not track:
            return

        try:
            pipeline = await bot.player.get_or_connect_pipeline(inter.author.voice.channel)
        except RuntimeError as e:
            return await inter.followup.send(f"⚠️ {e}", ephemeral=True)

        view = MusicControlView(bot.player)
        await inter.followup.send(f"Added to queue: **{track.title}**", view=view)
        await pipeline.enqueue_and_play(PlayableItem(track, mode="standard"))

    @shanty.sub_command(name="skip", description="Skip the current playing shanty")
    async def skip(inter: disnake.ApplicationCommandInteraction):
        if not inter.author.voice or not inter.author.voice.channel:
            await inter.response.send_message("Ye must be in a voice channel to skip tracks!", ephemeral=True)
            return

        pipeline = bot.player.get_pipeline(inter.author.voice.channel.id)
        if pipeline and pipeline.voice_client and (pipeline.voice_client.is_playing() or pipeline.voice_client.is_paused()):
            await pipeline.skip()
            await inter.response.send_message("Skipped to the next track!")
        else:
            await inter.response.send_message("Nothing is currently playing in your channel.")

    @shanty.sub_command(name="leave", description="Disconnect from your voice channel and clear the queue")
    async def leave(inter: disnake.ApplicationCommandInteraction):
        if not inter.author.voice or not inter.author.voice.channel:
            await inter.response.send_message("Ye must be in a voice channel to dismiss the bot!", ephemeral=True)
            return

        channel_id = inter.author.voice.channel.id
        pipeline = bot.player.get_pipeline(channel_id)

        if not pipeline:
            await inter.response.send_message("The crew is not currently in your voice channel.", ephemeral=True)
            return

        await bot.player.remove_pipeline(channel_id)
        await inter.response.send_message("👋 Left the voice channel and cleared the ship's queue!")

    @shanty.sub_command(name="reload", description="Reload the local media index")
    async def reload(inter: disnake.ApplicationCommandInteraction):
        count = bot.library.refresh_index()
        await inter.response.send_message(f"Library re-indexed! Found {count} music tracks and {len(bot.library.ambient_cache)} ambient tracks.")
