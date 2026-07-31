import asyncio
import logging
from pathlib import Path
import shutil

logger = logging.getLogger("shantyBot")

def _get_ffmpeg_executable() -> str:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    local_ffmpeg = Path("./ffmpeg.exe").resolve()
    if local_ffmpeg.exists():
        return str(local_ffmpeg)
    return "ffmpeg"

class OpusCacheIndex:
    """Manages Just-In-Time (JIT) Opus audio transcoding and LRU cache eviction."""
    def __init__(self, cache_dir: str = "./media/cache", max_cache_gb: float = 2.0):
        self.cache_dir = Path(cache_dir).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_cache_gb = max_cache_gb
        self._transcoding_locks: dict[str, asyncio.Lock] = {}

    def get_cache_path(self, source_path: Path) -> Path:
        """Derives cached .opus file path from source track stem."""
        safe_stem = source_path.stem.replace(" ", "_")
        return self.cache_dir / f"{safe_stem}.opus"

    def get_cached_opus(self, source_path: Path) -> Path | None:
        """Returns cached .opus file if available and non-empty."""
        cache_path = self.get_cache_path(source_path)
        if cache_path.exists() and cache_path.stat().st_size > 0:
            return cache_path
        return None

    async def ensure_cached_async(self, source_path: Path) -> Path | None:
        """Asynchronously transcodes source audio to .opus format in the background."""
        source_path = Path(source_path).resolve()
        if not source_path.exists():
            return None

        cache_path = self.get_cache_path(source_path)
        if cache_path.exists() and cache_path.stat().st_size > 0:
            return cache_path

        lock_key = str(cache_path)
        if lock_key not in self._transcoding_locks:
            self._transcoding_locks[lock_key] = asyncio.Lock()

        async with self._transcoding_locks[lock_key]:
            # Double check after acquiring lock
            if cache_path.exists() and cache_path.stat().st_size > 0:
                return cache_path

            ffmpeg_bin = _get_ffmpeg_executable()
            temp_cache_path = cache_path.with_suffix(".tmp.opus")

            cmd = [
                ffmpeg_bin,
                "-y",
                "-i", str(source_path),
                "-c:a", "libopus",
                "-b:a", "96k",
                "-ar", "48000",
                "-ac", "2",
                str(temp_cache_path)
            ]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await proc.wait()

                if proc.returncode == 0 and temp_cache_path.exists() and temp_cache_path.stat().st_size > 0:
                    temp_cache_path.replace(cache_path)
                    logger.info(f"Successfully cached Opus track: {cache_path.name}")
                    self._enforce_cache_quota()
                    return cache_path
                else:
                    if temp_cache_path.exists():
                        temp_cache_path.unlink(missing_ok=True)
                    logger.warning(f"FFmpeg Opus transcode failed for {source_path.name}")
            except Exception as e:
                logger.error(f"Error during Opus transcoding for {source_path.name}: {e}")
                if temp_cache_path.exists():
                    temp_cache_path.unlink(missing_ok=True)

        return None

    def _enforce_cache_quota(self):
        """Enforces LRU cache quota if max_cache_gb > 0."""
        if self.max_cache_gb <= 0:
            return

        max_bytes = int(self.max_cache_gb * 1024 * 1024 * 1024)
        cached_files = [f for f in self.cache_dir.glob("*.opus") if f.is_file()]
        total_size = sum(f.stat().st_size for f in cached_files)

        if total_size <= max_bytes:
            return

        # Sort by access time / modification time ascending (least recently used first)
        cached_files.sort(key=lambda f: f.stat().st_mtime)

        for file_path in cached_files:
            if total_size <= max_bytes:
                break
            try:
                size = file_path.stat().st_size
                file_path.unlink(missing_ok=True)
                total_size -= size
                logger.info(f"LRU Evicted cached Opus file: {file_path.name}")
            except Exception as e:
                logger.warning(f"Failed to evict cached file {file_path.name}: {e}")
