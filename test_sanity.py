import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.youtube import YouTubeIngestor
from core.audio_source import MixedAudioSource, _get_ffmpeg_executable
from core.library import LocalLibrary, Track
from web.server import _get_item_display_name
from main import ensure_directories

def test_track_metadata():
    t1 = Track(title="Wellerman", artist="Nathan Evans", path=Path("/fake/path.mp3"))
    assert t1.display_name == "Nathan Evans - Wellerman", "Display name with artist failed"

    t2 = Track(title="Leave Her Johnny", artist="Unknown Artist", path=Path("/fake/path.mp3"))
    assert t2.display_name == "Leave Her Johnny", "Display name fallback failed"
    print("✅ Track Metadata & Display Name Test Passed!")

def test_url_allowlist():
    ingestor = YouTubeIngestor(cache_dir="./media/cache", allowed_playlist_ids=["PL12345"])
    assert ingestor.is_url_allowed("https://www.youtube.com/watch?v=abc&list=PL12345") == True, "Allowed playlist failed"
    assert ingestor.is_url_allowed("https://www.youtube.com/watch?v=abc&list=PL99999") == False, "Blocked playlist failed"
    assert ingestor.is_url_allowed("https://vimeo.com/12345") == False, "Non-YouTube URL failed"
    
    open_ingestor = YouTubeIngestor(cache_dir="./media/cache", allowed_playlist_ids=[])
    assert open_ingestor.is_url_allowed("https://www.youtube.com/watch?v=abc") == True, "Open YT URL failed"
    assert open_ingestor.is_url_allowed("https://youtu.be/abc") == True, "Open youtu.be URL failed"
    print("✅ URL Allowlist Validation Passed!")

def test_directories():
    config = {
        "paths": {
            "media_directory": "./media/shanties",
            "raid_directory": "./media/raid_sounds",
            "ambient_directory": "./media/ambient",
            "youtube_cache_directory": "./media/cache"
        }
    }
    ensure_directories(config)
    for p in ["./media/shanties", "./media/raid_sounds", "./media/ambient", "./media/cache"]:
        assert Path(p).exists(), f"Directory {p} missing"
    print("✅ Directory Auto-Creation Validation Passed!")

def test_item_display_helper():
    t = Track(title="Drunken Sailor", artist="The Longest Johns", path=Path("/fake/path.mp3"))
    item = type("PlayableItem", (), {"track": t})()
    assert _get_item_display_name(item) == "The Longest Johns - Drunken Sailor"
    print("✅ Web Server Item Display Name Helper Passed!")

if __name__ == "__main__":
    test_track_metadata()
    test_url_allowlist()
    test_directories()
    test_item_display_helper()
    print("🎉 All shantyBot Sanity Checks Passed!")
