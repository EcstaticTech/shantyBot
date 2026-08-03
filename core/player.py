import asyncio
import logging
import random
import time
from pathlib import Path
from typing import Dict, Optional
import disnake
from core.audio_source import MixedAudioSource, SoloAmbientAudioSource
from core.library import Track, LocalLibrary
from core.cache_index import OpusCacheIndex

logger = logging.getLogger("shantyBot")

class PlayableItem:
    def __init__(self, track: Track, mode: str = "standard", seek_seconds: float = 0.0):
        self.track = track
        self.mode = mode
        self.seek_seconds = seek_seconds

class ChannelAudioPipeline:
    """Channel-isolated audio pipeline managing voice state, queue, ambient audio, and playback lock."""
    def __init__(
        self,
        channel_id: int,
        bot: disnake.Client,
        library: Optional[LocalLibrary] = None,
        voice_client: Optional[disnake.VoiceClient] = None,
        idle_timeout: int = 180,
        ambient_dir: Path = Path("./media/ambient"),
        cache_index: Optional[OpusCacheIndex] = None,
        on_destroy: Optional[callable] = None
    ):
        self.channel_id: int = channel_id
        self.bot: disnake.Client = bot
        self.library: Optional[LocalLibrary] = library
        self.voice_client: Optional[disnake.VoiceClient] = voice_client
        self.queue: list[PlayableItem] = []
        self.current_track: Optional[Track] = None
        self.current_source = None
        self.active_ambient: Optional[Track] = None
        self.shuffle_mode: bool = False
        self.last_played_path: Optional[Path] = None
        self.track_start_time: Optional[float] = None
        self.paused_at: Optional[float] = None
        self.total_paused_duration: float = 0.0
        self.duration_seconds: float = 0.0
        self.idle_timeout: int = idle_timeout
        self.ambient_dir: Path = Path(ambient_dir).resolve()
        self.cache_index: Optional[OpusCacheIndex] = cache_index
        self._on_destroy: Optional[callable] = on_destroy
        self._idle_task: Optional[asyncio.Task] = None
        self._playback_lock = asyncio.Lock()
        self._is_transitioning = False
        self._swapping_streams = False

    @property
    def is_paused(self) -> bool:
        return bool(self.paused_at is not None or (self.voice_client and self.voice_client.is_paused()))

    @property
    def elapsed_seconds(self) -> float:
        """Calculates drift-free elapsed playback seconds, adjusting for active pause duration."""
        if not self.current_track or self.track_start_time is None:
            return 0.0
        if self.paused_at is not None:
            now = self.paused_at
        else:
            now = time.time()
        elapsed = now - self.track_start_time - self.total_paused_duration
        if self.duration_seconds > 0:
            elapsed = min(elapsed, self.duration_seconds)
        return max(0.0, elapsed)

    @property
    def progress_str(self) -> str:
        """Formats real-time playback progress as mm:ss / mm:ss."""
        def fmt(s: float) -> str:
            m, sec = divmod(int(s), 60)
            return f"{m:02d}:{sec:02d}"
        if not self.current_track:
            return "00:00 / 00:00"
        elapsed = fmt(self.elapsed_seconds)
        duration = fmt(self.duration_seconds) if self.duration_seconds > 0 else "--:--"
        return f"{elapsed} / {duration}"

    def _make_after_callback(self):
        """Generates an after callback for voice_client.play that respects self._swapping_streams."""
        def after_cb(error: Optional[Exception]):
            if self._swapping_streams:
                logger.debug(f"Stream swap in progress [Channel {self.channel_id}]. Suppressing after callback.")
                return
            if self.bot and hasattr(self.bot, "loop") and self.bot.loop:
                self.bot.loop.call_soon_threadsafe(self.play_next, error)
        return after_cb

    async def pause(self):
        """Pauses playback. If ambient mode is active, transitions seamlessly to SoloAmbientAudioSource."""
        async with self._playback_lock:
            if not self.voice_client or not self.voice_client.is_connected():
                return

            if (self.voice_client.is_playing() or not self.is_paused) and self.paused_at is None:
                self.paused_at = time.time()
                if self.active_ambient and self.current_track:
                    self._swapping_streams = True
                    try:
                        self.cleanup_current_source()
                        self.voice_client.stop()
                        await asyncio.sleep(0.1)

                        source = SoloAmbientAudioSource(str(self.active_ambient.path), ambient_volume=0.5)
                        self.current_source = source
                        self.voice_client.play(source, after=self._make_after_callback())
                    except Exception as e:
                        logger.error(f"Error swapping to SoloAmbientAudioSource on pause [Channel {self.channel_id}]: {e}")
                    finally:
                        self._swapping_streams = False
                else:
                    self.voice_client.pause()

    async def resume(self):
        """Resumes playback. If solo ambient was active during pause, re-spawns MixedAudioSource with seek_seconds."""
        async with self._playback_lock:
            if not self.voice_client or not self.voice_client.is_connected():
                return

            if self.is_paused:
                seek = self.elapsed_seconds
                if self.paused_at is not None:
                    self.total_paused_duration += max(0.0, time.time() - self.paused_at)
                    self.paused_at = None

                if self.active_ambient and self.current_track:
                    self._swapping_streams = True
                    try:
                        self.cleanup_current_source()
                        self.voice_client.stop()
                        await asyncio.sleep(0.1)

                        main_path = self.current_track.path
                        if self.cache_index:
                            cached = self.cache_index.get_cached_opus(self.current_track.path)
                            if cached:
                                main_path = cached

                        source = MixedAudioSource(str(main_path), str(self.active_ambient.path), seek_seconds=seek)
                        self.current_source = source
                        self.voice_client.play(source, after=self._make_after_callback())
                    except Exception as e:
                        logger.error(f"Error resuming MixedAudioSource [Channel {self.channel_id}]: {e}")
                    finally:
                        self._swapping_streams = False
                else:
                    if self.voice_client.is_paused():
                        self.voice_client.resume()

    def cleanup_current_source(self):
        """Cleanly terminates child FFmpeg processes on current audio source."""
        if self.current_source and hasattr(self.current_source, "cleanup"):
            try:
                self.current_source.cleanup()
            except Exception as e:
                logger.warning(f"Error during current_source cleanup [Channel {self.channel_id}]: {e}")
        self.current_source = None

        if self.voice_client and self.voice_client.source and hasattr(self.voice_client.source, "cleanup"):
            try:
                self.voice_client.source.cleanup()
            except Exception as e:
                logger.warning(f"Error during voice_client.source cleanup [Channel {self.channel_id}]: {e}")

    def play_next(self, error: Optional[Exception] = None):
        """Advances the playback queue using state-machine evaluating queue state and active_ambient."""
        if error:
            logger.error(f"Playback error encountered [Channel {self.channel_id}]: {error}")

        if self._is_transitioning:
            logger.debug(f"Transition already in progress [Channel {self.channel_id}]. Skipping duplicate play_next.")
            return

        self._is_transitioning = True

        try:
            self.cleanup_current_source()

            if not self.voice_client or not self.voice_client.is_connected():
                self.current_track = None
                self.track_start_time = None
                self.paused_at = None
                self.total_paused_duration = 0.0
                self.duration_seconds = 0.0
                return

            # Case A: Track in Queue
            if self.queue:
                item = self.queue.pop(0)
                self.current_track = item.track
                self.last_played_path = item.track.path
                self.duration_seconds = getattr(item.track, "duration_seconds", 0.0)
                self.paused_at = None
                self.total_paused_duration = 0.0
                seek = getattr(item, "seek_seconds", 0.0)
                self.track_start_time = time.time() - seek

                main_track_path = item.track.path
                if self.cache_index:
                    cached_opus = self.cache_index.get_cached_opus(item.track.path)
                    if cached_opus:
                        main_track_path = cached_opus
                    else:
                        if self.bot and hasattr(self.bot, "loop") and self.bot.loop:
                            self.bot.loop.create_task(self.cache_index.ensure_cached_async(item.track.path))

                source = None
                if self.active_ambient is not None:
                    try:
                        source = MixedAudioSource(str(main_track_path), str(self.active_ambient.path), seek_seconds=seek)
                    except Exception as e:
                        logger.error(f"Error creating MixedAudioSource with active_ambient [Channel {self.channel_id}]: {e}")
                        source = None
                elif item.mode == "tavern":
                    ambient_file = self.ambient_dir / "tavern.mp3"
                    if ambient_file.exists():
                        try:
                            source = MixedAudioSource(str(main_track_path), str(ambient_file), seek_seconds=seek)
                        except Exception as e:
                            logger.error(f"Error creating MixedAudioSource tavern mode [Channel {self.channel_id}]: {e}")
                            source = None
                    else:
                        logger.warning(f"Ambient track {ambient_file} missing. Falling back to standard playback.")

                if source is None:
                    options = f"-ss {seek:.2f} -vn -filter:a 'volume=0.8'" if seek > 0 else "-vn -filter:a 'volume=0.8'"
                    source = disnake.FFmpegPCMAudio(str(main_track_path), options=options)

                self.current_source = source
                self.voice_client.play(source, after=self._make_after_callback())

            # Case B: Queue Empty + Shuffle Mode Active
            elif self.shuffle_mode:
                lib = self.library or getattr(self.bot, "library", None)
                tracks = getattr(lib, "cache", []) if lib else []

                candidates = [t for t in tracks if t.path != self.last_played_path]
                if not candidates and tracks:
                    # Fallback for 1-track library
                    candidates = list(tracks)

                if candidates:
                    selected_track = random.choice(candidates)
                    self.current_track = selected_track
                    self.last_played_path = selected_track.path
                    self.duration_seconds = getattr(selected_track, "duration_seconds", 0.0)
                    self.paused_at = None
                    self.total_paused_duration = 0.0
                    self.track_start_time = time.time()

                    if self._idle_task and not self._idle_task.done():
                        self._idle_task.cancel()

                    main_track_path = selected_track.path
                    if self.cache_index:
                        cached_opus = self.cache_index.get_cached_opus(selected_track.path)
                        if cached_opus:
                            main_track_path = cached_opus
                        else:
                            if self.bot and hasattr(self.bot, "loop") and self.bot.loop:
                                self.bot.loop.create_task(self.cache_index.ensure_cached_async(selected_track.path))

                    source = None
                    if self.active_ambient is not None:
                        try:
                            source = MixedAudioSource(str(main_track_path), str(self.active_ambient.path))
                        except Exception as e:
                            logger.error(f"Error creating MixedAudioSource for shuffle auto-pick [Channel {self.channel_id}]: {e}")
                            source = None

                    if source is None:
                        source = disnake.FFmpegPCMAudio(str(main_track_path), options="-vn -filter:a 'volume=0.8'")

                    self.current_source = source
                    self.voice_client.play(source, after=self._make_after_callback())
                else:
                    logger.warning(f"Shuffle mode active but media library is empty [Channel {self.channel_id}]. Disabling shuffle mode.")
                    self.shuffle_mode = False
                    if self.active_ambient is not None:
                        self.current_track = None
                        self.track_start_time = None
                        self.paused_at = None
                        self.total_paused_duration = 0.0
                        self.duration_seconds = 0.0
                        try:
                            source = SoloAmbientAudioSource(str(self.active_ambient.path), ambient_volume=0.5)
                        except Exception as e:
                            logger.error(f"Error creating SoloAmbientAudioSource [Channel {self.channel_id}]: {e}")
                            source = None

                        if source:
                            self.current_source = source
                            self.voice_client.play(source, after=self._make_after_callback())
                        else:
                            self._schedule_idle_disconnect()
                    else:
                        self.current_track = None
                        self.track_start_time = None
                        self.paused_at = None
                        self.total_paused_duration = 0.0
                        self.duration_seconds = 0.0
                        self._schedule_idle_disconnect()

            # Case C: Queue Empty + Ambient Active (Ambient Solo Loop)
            elif self.active_ambient is not None:
                self.current_track = None
                self.track_start_time = None
                self.paused_at = None
                self.total_paused_duration = 0.0
                self.duration_seconds = 0.0
                try:
                    source = SoloAmbientAudioSource(str(self.active_ambient.path), ambient_volume=0.5)
                except Exception as e:
                    logger.error(f"Error creating SoloAmbientAudioSource [Channel {self.channel_id}]: {e}")
                    source = None

                if source:
                    self.current_source = source
                    self.voice_client.play(source, after=self._make_after_callback())
                else:
                    self._schedule_idle_disconnect()

            # Case D: Queue Empty + Ambient Off
            else:
                self.current_track = None
                self.track_start_time = None
                self.paused_at = None
                self.total_paused_duration = 0.0
                self.duration_seconds = 0.0
                self._schedule_idle_disconnect()
        finally:
            self._is_transitioning = False

    async def enqueue_and_play(self, item: PlayableItem):
        """Enqueues an item and manages audio stream transition if in solo ambient loop or idle."""
        async with self._playback_lock:
            self.queue.append(item)
            if self.voice_client and self.voice_client.is_connected():
                if self.current_track is None:
                    # In Solo Ambient loop or Idle state: stop solo stream with callback suppression and kick off play_next immediately
                    if self.voice_client.is_playing() or self.is_paused:
                        self._swapping_streams = True
                        try:
                            self.cleanup_current_source()
                            self.voice_client.stop()
                            await asyncio.sleep(0.1)
                        finally:
                            self._swapping_streams = False
                    self.play_next()
                elif not self.voice_client.is_playing() and not self.is_paused:
                    self.play_next()

    async def set_ambient_mode(self, ambient_track: Optional[Track]):
        """Updates active_ambient state and performs in-place stream swap if actively playing."""
        async with self._playback_lock:
            self.active_ambient = ambient_track

            if not self.voice_client or not self.voice_client.is_connected():
                return

            # Scenario A: No main track playing (Idle or Solo Ambient Loop)
            if not self.current_track:
                self._swapping_streams = True
                try:
                    self.cleanup_current_source()
                    if self.voice_client.is_playing() or self.is_paused:
                        self.voice_client.stop()
                        await asyncio.sleep(0.1)

                    if self.active_ambient:
                        source = SoloAmbientAudioSource(str(self.active_ambient.path), ambient_volume=0.5)
                        self.current_source = source
                        self.voice_client.play(source, after=self._make_after_callback())
                    else:
                        self._schedule_idle_disconnect()
                finally:
                    self._swapping_streams = False
                return

            # Scenario B: Main track is PAUSED
            if self.is_paused:
                self._swapping_streams = True
                try:
                    self.cleanup_current_source()
                    if self.voice_client.is_playing() or self.voice_client.is_paused():
                        self.voice_client.stop()
                        await asyncio.sleep(0.1)
                    if self.active_ambient:
                        source = SoloAmbientAudioSource(str(self.active_ambient.path), ambient_volume=0.5)
                        self.current_source = source
                        self.voice_client.play(source, after=self._make_after_callback())
                finally:
                    self._swapping_streams = False
                return

            # Scenario C: Main track is ACTIVELY PLAYING (is_paused == False)
            try:
                self._swapping_streams = True
                elapsed = max(0.0, self.elapsed_seconds)

                self.cleanup_current_source()
                if self.voice_client.is_playing():
                    self.voice_client.stop()
                    await asyncio.sleep(0.1)

                main_path = self.current_track.path
                if self.cache_index:
                    cached = self.cache_index.get_cached_opus(self.current_track.path)
                    if cached:
                        main_path = cached

                if self.active_ambient:
                    new_source = MixedAudioSource(str(main_path), str(self.active_ambient.path), seek_seconds=elapsed)
                else:
                    options = f"-ss {elapsed:.2f} -vn -filter:a 'volume=0.8'" if elapsed > 0 else "-vn -filter:a 'volume=0.8'"
                    new_source = disnake.FFmpegPCMAudio(str(main_path), options=options)

                self.current_source = new_source
                self.voice_client.play(new_source, after=self._make_after_callback())
                self.track_start_time = time.time() - elapsed
            except Exception as e:
                logger.error(f"Error during mid-track ambient swap [Channel {self.channel_id}]: {e}")
            finally:
                self._swapping_streams = False

    async def skip(self):
        """Cancels pending idle tasks and stops voice client playback cleanly."""
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()

        if self.voice_client:
            if self.voice_client.is_playing() or self.is_paused:
                self.voice_client.stop()
            else:
                self.play_next()

    def _schedule_idle_disconnect(self):
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        if self.bot and hasattr(self.bot, "loop") and self.bot.loop:
            self._idle_task = self.bot.loop.create_task(self._idle_disconnect())

    async def _idle_disconnect(self):
        await asyncio.sleep(self.idle_timeout)
        if self.voice_client and not self.voice_client.is_playing() and not self.queue and self.active_ambient is None:
            await self.cleanup()

    async def trigger_raid_interrupt(self, raid_item: PlayableItem):
        """Subprocess-safe raid interrupt handler guarding against concurrent track transitions."""
        async with self._playback_lock:
            if self._idle_task and not self._idle_task.done():
                self._idle_task.cancel()

            self.queue.insert(0, raid_item)

            if self.voice_client and (self.voice_client.is_playing() or self.is_paused):
                self._swapping_streams = True
                try:
                    self.voice_client.stop()
                    await asyncio.sleep(0.15)
                finally:
                    self._swapping_streams = False
            else:
                self.play_next()

    async def cleanup(self):
        """Flushes queue, stops audio source, disconnects voice client, and notifies manager."""
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()

        self.cleanup_current_source()
        self.queue.clear()
        self.current_track = None
        self.track_start_time = None
        self.paused_at = None
        self.total_paused_duration = 0.0
        self.duration_seconds = 0.0

        if self.voice_client and self.voice_client.is_connected():
            try:
                await self.voice_client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting voice_client [Channel {self.channel_id}]: {e}")
        self.voice_client = None

        if self._on_destroy:
            try:
                self._on_destroy(self.channel_id)
            except Exception as e:
                logger.warning(f"Error in on_destroy callback for channel {self.channel_id}: {e}")

class ShantyPlayer:
    """Multi-channel Manager & Backward-Compatible Facade for shantyBot Audio Engine."""
    def __init__(
        self,
        bot: disnake.Client,
        library: Optional[LocalLibrary] = None,
        idle_timeout: int = 180,
        ambient_dir: str = "./media/ambient",
        cache_dir: str = "./media/cache",
        max_cache_gb: float = 2.0,
        max_channels: int = 2
    ):
        self.bot = bot
        self.library = library
        self.idle_timeout = idle_timeout
        self.ambient_dir = Path(ambient_dir).resolve()
        self.max_channels = max_channels
        self.cache_index = OpusCacheIndex(cache_dir=cache_dir, max_cache_gb=max_cache_gb)
        self.pipelines: Dict[int, ChannelAudioPipeline] = {}
        self._default_channel_id = 0

    def get_pipeline(self, channel_id: int) -> Optional[ChannelAudioPipeline]:
        return self.pipelines.get(channel_id)

    def get_or_create_pipeline(
        self,
        channel_id: int,
        voice_channel: Optional[disnake.VoiceChannel] = None
    ) -> ChannelAudioPipeline:
        if channel_id in self.pipelines:
            return self.pipelines[channel_id]

        if len(self.pipelines) >= self.max_channels:
            raise RuntimeError(f"Maximum active channel limit ({self.max_channels}) reached.")

        pipeline = ChannelAudioPipeline(
            channel_id=channel_id,
            bot=self.bot,
            library=self.library,
            voice_client=None,
            idle_timeout=self.idle_timeout,
            ambient_dir=self.ambient_dir,
            cache_index=self.cache_index,
            on_destroy=self._remove_pipeline_sync
        )
        self.pipelines[channel_id] = pipeline
        return pipeline

    async def get_or_connect_pipeline(
        self,
        voice_channel: disnake.VoiceChannel
    ) -> ChannelAudioPipeline:
        channel_id = voice_channel.id
        if channel_id in self.pipelines:
            pipeline = self.pipelines[channel_id]
            if not pipeline.voice_client or not pipeline.voice_client.is_connected():
                pipeline.voice_client = await voice_channel.connect()
            return pipeline

        if len(self.pipelines) >= self.max_channels:
            raise RuntimeError(f"Maximum active channel limit ({self.max_channels}) reached.")

        voice_client = await voice_channel.connect()
        pipeline = ChannelAudioPipeline(
            channel_id=channel_id,
            bot=self.bot,
            library=self.library,
            voice_client=voice_client,
            idle_timeout=self.idle_timeout,
            ambient_dir=self.ambient_dir,
            cache_index=self.cache_index,
            on_destroy=self._remove_pipeline_sync
        )
        self.pipelines[channel_id] = pipeline
        return pipeline

    def _remove_pipeline_sync(self, channel_id: int):
        if channel_id in self.pipelines:
            del self.pipelines[channel_id]

    async def remove_pipeline(self, channel_id: int):
        if channel_id in self.pipelines:
            pipeline = self.pipelines[channel_id]
            await pipeline.cleanup()

    async def cleanup_all_pipelines(self):
        """Cleanly terminates all active channel pipelines, FFmpeg subprocesses, and voice clients."""
        channel_ids = list(self.pipelines.keys())
        for channel_id in channel_ids:
            if channel_id in self.pipelines:
                try:
                    await self.pipelines[channel_id].cleanup()
                except Exception as e:
                    logger.warning(f"Error during pipeline cleanup for channel {channel_id}: {e}")
        self.pipelines.clear()

    # --- Backward Compatibility Properties & Methods ---
    @property
    def primary_pipeline(self) -> ChannelAudioPipeline:
        if self.pipelines:
            return next(iter(self.pipelines.values()))
        if self._default_channel_id not in self.pipelines:
            self.pipelines[self._default_channel_id] = ChannelAudioPipeline(
                channel_id=self._default_channel_id,
                bot=self.bot,
                library=self.library,
                idle_timeout=self.idle_timeout,
                ambient_dir=self.ambient_dir,
                cache_index=self.cache_index,
                on_destroy=self._remove_pipeline_sync
            )
        return self.pipelines[self._default_channel_id]

    @property
    def queue(self) -> list[PlayableItem]:
        return self.primary_pipeline.queue

    @queue.setter
    def queue(self, value: list[PlayableItem]):
        self.primary_pipeline.queue = value

    @property
    def current_track(self) -> Optional[Track]:
        return self.primary_pipeline.current_track

    @current_track.setter
    def current_track(self, value: Optional[Track]):
        self.primary_pipeline.current_track = value

    @property
    def current_source(self):
        return self.primary_pipeline.current_source

    @current_source.setter
    def current_source(self, value):
        self.primary_pipeline.current_source = value

    @property
    def active_ambient(self) -> Optional[Track]:
        return self.primary_pipeline.active_ambient

    @active_ambient.setter
    def active_ambient(self, value: Optional[Track]):
        self.primary_pipeline.active_ambient = value

    @property
    def voice_client(self) -> Optional[disnake.VoiceClient]:
        return self.primary_pipeline.voice_client

    @voice_client.setter
    def voice_client(self, value: Optional[disnake.VoiceClient]):
        self.primary_pipeline.voice_client = value

    @property
    def elapsed_seconds(self) -> float:
        return self.primary_pipeline.elapsed_seconds

    @property
    def duration_seconds(self) -> float:
        return self.primary_pipeline.duration_seconds

    @property
    def progress_str(self) -> str:
        return self.primary_pipeline.progress_str

    @property
    def _playback_lock(self) -> asyncio.Lock:
        return self.primary_pipeline._playback_lock

    async def pause(self):
        await self.primary_pipeline.pause()

    async def resume(self):
        await self.primary_pipeline.resume()

    def cleanup_current_source(self):
        self.primary_pipeline.cleanup_current_source()

    def play_next(self, error: Optional[Exception] = None):
        self.primary_pipeline.play_next(error)

    async def set_ambient_mode(self, ambient_track: Optional[Track]):
        await self.primary_pipeline.set_ambient_mode(ambient_track)

    async def skip(self):
        await self.primary_pipeline.skip()

    async def trigger_raid_interrupt(self, raid_item: PlayableItem):
        await self.primary_pipeline.trigger_raid_interrupt(raid_item)

    async def trigger_raid(self, voice_channel: disnake.VoiceChannel) -> bool:
        raid_dir = Path(self.bot.raid_path if hasattr(self.bot, "raid_path") else "./media/raid_sounds").resolve()
        if not raid_dir.exists():
            logger.warning(f"Raid directory {raid_dir} does not exist.")
            return False

        raid_files = [f for f in raid_dir.glob("*") if f.is_file() and f.suffix.lower() in [".mp3", ".flac", ".opus", ".m4a", ".wav"]]
        if not raid_files:
            logger.warning("No audio files found in raid directory.")
            return False

        raid_sound = random.choice(raid_files)
        pipeline = await self.get_or_connect_pipeline(voice_channel)

        title = f"🏴‍☠️ RAID: {raid_sound.stem.replace('_', ' ').replace('-', ' ').title()}"
        raid_track = Track(title=title, artist="Raid Party", path=raid_sound)
        raid_item = PlayableItem(raid_track, mode="standard")

        await pipeline.trigger_raid_interrupt(raid_item)
        return True
