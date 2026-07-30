import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.youtube import YouTubeIngestor
from core.audio_source import MixedAudioSource
from main import ensure_directories

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

if __name__ == "__main__":
    test_url_allowlist()
    test_directories()
    print("🎉 All Sprint 2 Unit Tests Succeeded!")
