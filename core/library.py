import logging
from pathlib import Path
import re
from mutagen import File as MutagenFile

logger = logging.getLogger("shantyBot")

class Track:
    def __init__(self, title: str, artist: str, path: Path):
        self.title = title
        self.artist = artist
        self.path = path

    @property
    def display_name(self) -> str:
        if self.artist and self.artist != "Unknown Artist":
            return f"{self.artist} - {self.title}"
        return self.title

class LocalLibrary:
    def __init__(self, base_path: str, ambient_path: str = "./media/ambient"):
        self.base_path = Path(base_path).resolve()
        self.ambient_path = Path(ambient_path).resolve()
        self.cache: list[Track] = []
        self.ambient_cache: list[Track] = []
        self.refresh_index()

    def refresh_index(self) -> int:
        """Indexes local audio and ambient files into memory with Mutagen metadata parsing."""
        new_cache = []
        if not self.base_path.exists():
            logger.warning(f"Media directory {self.base_path} does not exist.")
            self.cache = []
        else:
            for file_path in self.base_path.glob("**/*"):
                if file_path.is_file() and file_path.suffix.lower() in [".mp3", ".flac", ".opus", ".m4a", ".wav"]:
                    resolved = file_path.resolve()
                    if self.base_path in resolved.parents or resolved == self.base_path:
                        title, artist = self._extract_metadata(resolved)
                        new_cache.append(Track(title=title, artist=artist, path=resolved))
            self.cache = new_cache

        new_ambient_cache = []
        if self.ambient_path.exists():
            for file_path in self.ambient_path.glob("**/*"):
                if file_path.is_file() and file_path.suffix.lower() in [".mp3", ".flac", ".opus", ".m4a", ".wav"]:
                    resolved = file_path.resolve()
                    if self.ambient_path in resolved.parents or resolved == self.ambient_path:
                        title, artist = self._extract_metadata(resolved)
                        new_ambient_cache.append(Track(title=title, artist="Ambient", path=resolved))
        self.ambient_cache = new_ambient_cache

        logger.info(f"Indexed {len(self.cache)} music tracks and {len(self.ambient_cache)} ambient tracks into memory.")
        return len(self.cache)

    def _extract_metadata(self, file_path: Path) -> tuple[str, str]:
        """Extracts title and artist tags using Mutagen with clean filename fallback."""
        fallback_title = file_path.stem.replace("_", " ").replace("-", " ").title()
        try:
            audio = MutagenFile(file_path)
            if audio is not None:
                title = audio.get("TIT2", [None])[0] or audio.get("title", [None])[0] or fallback_title
                artist = audio.get("TPE1", [None])[0] or audio.get("artist", [None])[0] or "Unknown Artist"
                return str(title), str(artist)
        except Exception as e:
            logger.debug(f"Mutagen metadata read failed for {file_path.name}: {e}")
        
        return fallback_title, "Unknown Artist"

    def search(self, query: str) -> Track | None:
        """Sub-millisecond in-memory string matching for music library."""
        clean_query = re.sub(r'[^\w\s\.-]', '', query).strip().lower()
        if not clean_query:
            return None

        for track in self.cache:
            if (clean_query in track.display_name.lower() or 
                clean_query in track.title.lower() or 
                clean_query in track.artist.lower() or 
                clean_query in track.path.stem.lower()):
                return track
        return None

    def search_ambient(self, query: str) -> Track | None:
        """Sub-millisecond in-memory string matching for ambient tracks."""
        clean_query = re.sub(r'[^\w\s\.-]', '', query).strip().lower()
        if not clean_query:
            return None

        for track in self.ambient_cache:
            if (clean_query in track.display_name.lower() or 
                clean_query in track.title.lower() or 
                clean_query in track.path.stem.lower()):
                return track
        return None
