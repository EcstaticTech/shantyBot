import re
import asyncio
from pathlib import Path
import logging
from yt_dlp import YoutubeDL
from core.library import Track

logger = logging.getLogger("shantyBot")

class YouTubeIngestor:
    def __init__(self, cache_dir: str, allowed_playlist_ids: list[str] | None = None, max_cache_bytes: int = 1073741824):
        self.cache_dir = Path(cache_dir).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.allowed_playlist_ids = allowed_playlist_ids or []
        self.max_cache_bytes = max_cache_bytes
        
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(self.cache_dir / '%(id)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'opus',
                'preferredquality': '0',
            }],
            'quiet': True,
            'no_warnings': True,
        }

    def is_url_allowed(self, url: str) -> bool:
        """Strict regex validation ensuring URLs match approved YouTube formats and playlists."""
        domain_match = re.match(r'^https?://(www\.)?(youtube\.com|youtu\.be)/', url, re.IGNORECASE)
        if not domain_match:
            return False

        if self.allowed_playlist_ids:
            playlist_match = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', url)
            if not playlist_match or playlist_match.group(1) not in self.allowed_playlist_ids:
                return False

        return True

    def purge_cache(self) -> int:
        """Purges oldest cached opus files if cache directory exceeds max_cache_bytes."""
        if not self.cache_dir.exists():
            return 0

        files = sorted(
            [f for f in self.cache_dir.glob("*.opus") if f.is_file()],
            key=lambda p: p.stat().st_mtime
        )
        total_size = sum(f.stat().st_size for f in files)
        purged_count = 0

        while total_size > self.max_cache_bytes and files:
            oldest_file = files.pop(0)
            file_size = oldest_file.stat().st_size
            try:
                oldest_file.unlink()
                total_size -= file_size
                purged_count += 1
                logger.info(f"Purged cached opus track {oldest_file.name} ({file_size} bytes)")
            except Exception as e:
                logger.warning(f"Failed to purge cached file {oldest_file.name}: {e}")

        return purged_count

    async def fetch_track(self, url: str) -> Track | None:
        """Downloads/fetches YouTube audio track asynchronously into cache without blocking event loop."""
        if not self.is_url_allowed(url):
            logger.warning(f"Blocked unauthorized URL ingestion attempt: {url}")
            return None

        # Execute automated cache purge check before download
        self.purge_cache()

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._extract_and_download, url)

    def _extract_and_download(self, url: str) -> Track | None:
        try:
            with YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None
                
                if info.get("_type") == "playlist" and "entries" in info and info["entries"]:
                    info = info["entries"][0]

                video_id = info.get("id")
                title = info.get("title", "Unknown Shanty")
                uploader = info.get("uploader") or info.get("channel") or "YouTube"
                expected_file = self.cache_dir / f"{video_id}.opus"
                
                if expected_file.exists():
                    logger.info(f"Cache hit for YouTube track {video_id}")
                    return Track(title=title, artist=uploader, path=expected_file)
                
                # Download missing file
                ydl.download([url])
                if expected_file.exists():
                    return Track(title=title, artist=uploader, path=expected_file)
        except Exception as e:
            logger.error(f"yt-dlp extraction failure for {url}: {e}")
        return None
