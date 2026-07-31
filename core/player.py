import asyncio
import logging
import random
from pathlib import Path
import disnake
from core.audio_source import MixedAudioSource
from core.library import Track

logger = logging.getLogger("shantyBot")

class PlayableItem:
    def __init__(self, track: Track, mode: str = "standard"):
        self.track = track
        self.mode = mode

class ShantyPlayer:
    def __init__(self, bot: disnake.Client, idle_timeout: int = 180, ambient_dir: str = "./media/ambient"):
        self.bot = bot
        self.queue: list[PlayableItem] = []
        self.current_track = None
        self.current_source = None
        self.active_ambient: Track | None = None
        self.voice_client: disnake.VoiceClient | None = None
        self.idle_timeout = idle_timeout
        self.ambient_dir = Path(ambient_dir).resolve()
        self._idle_task: asyncio.Task | None = None
        self._playback_lock = asyncio.Lock()
        self._is_transitioning = False

    def cleanup_current_source(self):
        """Cleanly terminates child FFmpeg processes on current audio source."""
        if self.current_source and hasattr(self.current_source, "cleanup"):
            try:
                self.current_source.cleanup()
            except Exception as e:
                logger.warning(f"Error during current_source cleanup: {e}")
        self.current_source = None

        if self.voice_client and self.voice_client.source and hasattr(self.voice_client.source, "cleanup"):
            try:
                self.voice_client.source.cleanup()
            except Exception as e:
                logger.warning(f"Error during voice_client.source cleanup: {e}")

    def play_next(self, error: Exception | None = None):
        """Advances the playback queue using a state-machine evaluating queue state and active_ambient."""
        if error:
            logger.error(f"Playback error encountered: {error}")

        if self._is_transitioning:
            logger.debug("Transition already in progress. Skipping duplicate play_next call.")
            return

        self._is_transitioning = True

        try:
            # Ensure previous process handles and pipes are released
            self.cleanup_current_source()

            if not self.voice_client or not self.voice_client.is_connected():
                self.current_track = None
                return

            # Case A: Track in Queue
            if self.queue:
                item = self.queue.pop(0)
                self.current_track = item.track
                
                source = None
                if self.active_ambient is not None:
                    try:
                        source = MixedAudioSource(str(item.track.path), str(self.active_ambient.path))
                    except Exception as e:
                        logger.error(f"Error creating MixedAudioSource with active_ambient: {e}")
                        source = None
                elif item.mode == "tavern":
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

            # Case B: Queue Empty + Ambient Active (Ambient Solo Loop)
            elif self.active_ambient is not None:
                self.current_track = self.active_ambient
                options = "-stream_loop -1 -vn -filter:a 'volume=0.5'"
                source = disnake.FFmpegPCMAudio(str(self.active_ambient.path), options=options)
                self.current_source = source
                self.voice_client.play(
                    source,
                    after=lambda e: self.bot.loop.call_soon_threadsafe(self.play_next, e)
                )

            # Case C: Queue Empty + Ambient Off
            else:
                self.current_track = None
                self._schedule_idle_disconnect()
        finally:
            self._is_transitioning = False

    async def set_ambient_mode(self, ambient_track: Track | None):
        """Updates active_ambient state and triggers immediate playback state re-evaluation."""
        async with self._playback_lock:
            self.active_ambient = ambient_track
            if self.voice_client and self.voice_client.is_connected():
                if self.voice_client.is_playing() or self.voice_client.is_paused():
                    # Stop active stream to force play_next() to re-evaluate state with new ambient setting
                    self.voice_client.stop()
                    await asyncio.sleep(0.15)
                else:
                    self.play_next()

    async def skip(self):
        """Explicitly cancels pending idle tasks and stops voice client playback cleanly."""
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()

        if self.voice_client:
            if self.voice_client.is_playing() or self.voice_client.is_paused():
                self.voice_client.stop()
            else:
                self.play_next()

    def _schedule_idle_disconnect(self):
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = self.bot.loop.create_task(self._idle_disconnect())

    async def _idle_disconnect(self):
        await asyncio.sleep(self.idle_timeout)
        if self.voice_client and not self.voice_client.is_playing() and not self.queue and self.active_ambient is None:
            self.cleanup_current_source()
            await self.voice_client.disconnect()
            self.voice_client = None
            logger.info("Disconnected from voice channel due to inactivity.")

    async def trigger_raid_interrupt(self, raid_item: PlayableItem):
        """Subprocess-safe raid interrupt handler guarding against concurrent track transitions."""
        async with self._playback_lock:
            if self._idle_task and not self._idle_task.done():
                self._idle_task.cancel()

            self.queue.insert(0, raid_item)

            if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
                self.voice_client.stop()
                await asyncio.sleep(0.15)
            else:
                self.play_next()

    async def trigger_raid(self, voice_channel: disnake.VoiceChannel) -> bool:
        """Triggers raid audio playback, interrupting active playback without process handle leaks."""
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

        title = f"🏴‍☠️ RAID: {raid_sound.stem.replace('_', ' ').replace('-', ' ').title()}"
        raid_track = Track(title=title, artist="Raid Party", path=raid_sound)
        raid_item = PlayableItem(raid_track, mode="standard")

        await self.trigger_raid_interrupt(raid_item)
        return True
