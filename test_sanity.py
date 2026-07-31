import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config_validator import validate_preflight_config
from core.youtube import YouTubeIngestor
from core.audio_source import MixedAudioSource, _get_ffmpeg_executable
from core.library import LocalLibrary, Track
from web.server import _get_item_display_name, create_web_app
from main import ensure_directories

def test_preflight_validator():
    # Case A: Default Placeholder
    case_a = {"bot": {"token": "YOUR_DISCORD_BOT_TOKEN_HERE"}}
    assert validate_preflight_config(case_a) == False, "Case A placeholder check failed"

    # Case B: Malformed String
    case_b = {"bot": {"token": "abc123invalid"}}
    assert validate_preflight_config(case_b) == False, "Case B malformed token check failed"

    # Case C: Valid Token Format
    case_c = {"bot": {"token": "MTEyMzQ1Njc4OTAxMjM0NTY3ODkuRzEyMzQ1LlNhbXBsZUhtYWNTaWduYXR1cmVTdHJpbmc5ODc2NQ"}}
    assert validate_preflight_config(case_c) == True, "Case C valid token check failed"

    print("✅ Pre-Flight Validator Tests Passed (Cases A, B, C)!")

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

def test_web_server_app():
    dummy_player = type("DummyPlayer", (), {"current_track": None, "active_ambient": None, "queue": [], "voice_client": None})()
    dummy_library = type("DummyLibrary", (), {"cache": []})()
    app = create_web_app(dummy_player, dummy_library)
    assert app is not None, "FastAPI app creation failed"
    print("✅ FastAPI Web Server App Creation Passed!")

def test_music_control_view():
    from core.views import MusicControlView
    dummy_player = type("DummyPlayer", (), {})()
    view = MusicControlView(dummy_player)
    custom_ids = [child.custom_id for child in view.children if hasattr(child, "custom_id")]
    assert "shanty_pause_resume" in custom_ids, "shanty_pause_resume custom_id missing"
    assert "shanty_skip" in custom_ids, "shanty_skip custom_id missing"
    assert "shantybot:raid" not in custom_ids and "shanty_raid" not in custom_ids, "Raid button should be removed"
    assert view.timeout is None, "View timeout must be None for persistence"
    print("✅ MusicControlView Buttons & Persistence Test Passed!")

def test_player_lock_and_interrupt():
    from core.player import ShantyPlayer
    dummy_bot = type("DummyBot", (), {"raid_path": "./media/raid_sounds"})()
    player = ShantyPlayer(dummy_bot)
    assert hasattr(player, "_playback_lock"), "player missing _playback_lock"
    assert hasattr(player, "trigger_raid_interrupt"), "player missing trigger_raid_interrupt"
    assert hasattr(player, "skip"), "player missing skip"
    print("✅ ShantyPlayer Lock & Raid Interrupt Methods Passed!")

def test_active_ambient_state_machine():
    from core.player import ShantyPlayer
    dummy_bot = type("DummyBot", (), {"raid_path": "./media/raid_sounds"})()
    player = ShantyPlayer(dummy_bot)
    assert hasattr(player, "active_ambient"), "player missing active_ambient"
    assert hasattr(player, "set_ambient_mode"), "player missing set_ambient_mode"
    assert player.active_ambient is None, "active_ambient default should be None"
    print("✅ ShantyPlayer Active Ambient State Machine Passed!")

def test_library_ambient_cache():
    lib = LocalLibrary("./media/shanties", "./media/ambient")
    assert hasattr(lib, "ambient_cache"), "library missing ambient_cache"
    assert hasattr(lib, "search_ambient"), "library missing search_ambient"
    print("✅ LocalLibrary Ambient Cache & Search Test Passed!")

if __name__ == "__main__":
    test_preflight_validator()
    test_track_metadata()
    test_url_allowlist()
    test_directories()
    test_item_display_helper()
    test_web_server_app()
    test_music_control_view()
    test_player_lock_and_interrupt()
    test_active_ambient_state_machine()
    test_library_ambient_cache()
    print("🎉 All shantyBot Sanity Checks Passed!")
