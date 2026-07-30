import asyncio
import logging
import random
from pathlib import Path
import disnake
from core.audio_source import MixedAudioSource

logger = logging.getLogger("shantyBot")

class PlayableItem:
    def __init__(self, track, mode: str = "standard"):
        self.track = track
        self.mode = mode

class ShantyPlayer:
    def __init__(self, bot: disnake.Client, idle_timeout: int = 180, ambient_dir: str = "./media/ambient"):
        self.bot = bot
        self.queue: list[PlayableItem] = []
        self.current_track = None
        self.current_source = None
        self.voice_client: disnake.VoiceClient | None = None
        self.idle_timeout = idle_timeout
        self.ambient_dir = Path(ambient_dir).resolve()
        self._idle_task: asyncio.Task | None = None

    def cleanup_current_source(self):
        """Cleanly terminates child FFmpeg processes on current audio source."""
        if self.current_source and hasattr(self.current_source, "cleanup"):
            try:
                self.current_source.cleanup()
            except Exception as e:
                logger.warning(f"Error during audio source cleanup: {e}")
        self.current_source = None

    def play_next(self, error: Exception | None = None):
        if error:
            logger.error(f"Playback error encountered: {error}")

        # Ensure previous process handle is killed
        self.cleanup_current_source()

        if self.queue and self.voice_client and self.voice_client.is_connected():
            item = self.queue.pop(0)
            self.current_track = item.track
            
            source = None
            if item.mode == "tavern":
                ambient_file = self.ambient_dir / "tavern.mp3"
                if ambient_file.exists():
                    try:
                        source = MixedAudioSource(str(item.track.path), str(ambient_file))
                    except Exception as e:
                        logger.error(f"Error creating MixedAudioSource, falling back to standard: {e}")
                        source = None
                else:
                    logger.warning(f"Ambient track {ambient_file} missing. Falling back to standard playback.")

            if source is None:
                options = "-vn -filter:a 'volume=0.8'"
                source = disnake.FFmpegPCMAudio(str(item.track.path), options=options)

            self.current_source = source
            self.voice_client.play(
                source,
                after=lambda e: self.bot.loop.call_soon_threadsafe(self.play_next, e)
            )
        else:
            self.current_track = None
            self._schedule_idle_disconnect()

    def _schedule_idle_disconnect(self):
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = self.bot.loop.create_task(self._idle_disconnect())

    async def _idle_disconnect(self):
        await asyncio.sleep(self.idle_timeout)
        if self.voice_client and not self.voice_client.is_playing() and not self.queue:
            self.cleanup_current_source()
            await self.voice_client.disconnect()
            self.voice_client = None
            logger.info("Disconnected from voice channel due to inactivity.")

    async def trigger_raid(self, voice_channel: disnake.VoiceChannel) -> bool:
        """Triggers raid audio playback, stopping current track if active."""
        raid_dir = Path(self.bot.raid_path).resolve()
        if not raid_dir.exists():
            logger.warning(f"Raid directory {raid_dir} does not exist.")
            return False

        raid_files = [f for f in raid_dir.glob("*") if f.is_file() and f.suffix.lower() in [".mp3", ".flac", ".opus", ".m4a", ".wav"]]
        if not raid_files:
            logger.warning("No audio files found in raid directory.")
            return False

        raid_sound = random.choice(raid_files)
        
        if not self.voice_client or not self.voice_client.is_connected():
            self.voice_client = await voice_channel.connect()

        self.cleanup_current_source()
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()

        options = "-vn -filter:a 'volume=1.0'"
        source = disnake.FFmpegPCMAudio(str(raid_sound), options=options)
        self.current_source = source
        self.current_track = type("RaidTrack", (), {"title": f"🏴‍☠️ RAID: {raid_sound.stem.title()}"})()

        self.voice_client.play(
            source,
            after=lambda e: self.bot.loop.call_soon_threadsafe(self.play_next, e)
        )
        return True
