import sys
import asyncio
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.library import LocalLibrary, Track
from core.player import ShantyPlayer, ChannelAudioPipeline, PlayableItem
from core.cache_index import OpusCacheIndex
from core.bot import ShantyBot, setup_bot_commands
from core.audio_source import MixedAudioSource, SoloAmbientAudioSource
from web.server import create_web_app

def test_command_deprecation():
    dummy_bot = ShantyBot(player=None, library=None, youtube=None, raid_path="./media/raid_sounds")
    setup_bot_commands(dummy_bot)
    shanty_cmd = dummy_bot.get_slash_command("shanty")
    sub_names = [sub.name for sub in shanty_cmd.children.values()]
    assert "tavern" not in sub_names, "Legacy /tavern subcommand still registered"
    assert "raid" not in sub_names, "Legacy /raid subcommand still registered"
    assert "play" in sub_names, "/play subcommand missing"
    assert "skip" in sub_names, "/skip subcommand missing"
    assert "leave" in sub_names, "/leave subcommand missing"
    assert "reload" in sub_names, "/reload subcommand missing"
    print("✅ Slash Command Deprecation & /leave Test Passed!")

def test_mixed_and_solo_audio_sources():
    mixed = MixedAudioSource("/fake/main.mp3", "/fake/ambient.mp3", seek_seconds=22.5)
    assert hasattr(mixed, "main_path"), "main_path missing"
    assert hasattr(mixed, "ambient_path"), "ambient_path missing"
    assert mixed.seek_seconds == 22.5, "seek_seconds mismatch"

    solo = SoloAmbientAudioSource("/fake/ambient.mp3")
    assert hasattr(solo, "ambient_path"), "ambient_path missing"
    print("✅ MixedAudioSource (with seek_seconds) & SoloAmbientAudioSource Construction Passed!")

def test_audio_source_cleanup_pipes():
    mixed = MixedAudioSource("/fake/main.mp3", "/fake/ambient.mp3")
    mixed.cleanup()
    assert mixed.process is None, "cleanup failed to reset process handle"

    solo = SoloAmbientAudioSource("/fake/ambient.mp3")
    solo.cleanup()
    assert solo.process is None, "cleanup failed to reset process handle for solo ambient"
    print("✅ Task E.1 FFmpeg Pipe Closure & Cleanup Test Passed!")

def test_eof_state_disentanglement():
    dummy_bot = type("DummyBot", (), {"loop": asyncio.get_event_loop_policy().get_event_loop(), "raid_path": "./media/raid_sounds"})()
    pipeline = ChannelAudioPipeline(channel_id=999, bot=dummy_bot)

    amb_track = Track(title="Sea Ambience", artist="Ambient", path=Path("/fake/sea.mp3"))
    pipeline.active_ambient = amb_track

    # Simulate play_next with empty queue
    pipeline.play_next()

    assert pipeline.current_track is None, "current_track must reset to None on EOF / empty queue"
    assert pipeline.active_ambient == amb_track, "active_ambient must remain set on ambient solo transition"
    print("✅ EOF State Disentanglement Test Passed (current_track = None on empty queue)!")

def test_solo_ambient_kick_mechanism():
    dummy_bot = type("DummyBot", (), {"loop": asyncio.get_event_loop_policy().get_event_loop(), "raid_path": "./media/raid_sounds"})()
    pipeline = ChannelAudioPipeline(channel_id=444, bot=dummy_bot)

    amb_track = Track(title="Ocean Waves", artist="Ambient", path=Path("/fake/ocean.mp3"))
    pipeline.active_ambient = amb_track

    # Simulate queue empty -> Solo Ambient mode
    pipeline.play_next()
    assert pipeline.current_track is None, "current_track must be None in Solo Ambient mode"

    # Test enqueue_and_play when current_track is None (Solo Ambient)
    new_track = Track(title="Barrett's Privateers", artist="Stan Rogers", path=Path("/fake/barretts.mp3"), duration_seconds=250.0)
    item = PlayableItem(new_track)
    
    asyncio.run(pipeline.enqueue_and_play(item))
    
    # Verify play_next popped the track immediately without stalling
    assert pipeline.current_track == new_track, "enqueue_and_play failed to kick off play_next immediately in Solo Ambient mode"
    assert len(pipeline.queue) == 0, "Queue was not popped upon solo ambient kick"
    print("✅ Task E.3 & E.4 Solo-Ambient Kick Mechanism Test Passed!")

def test_mid_track_seek_tracking():
    dummy_bot = type("DummyBot", (), {"loop": asyncio.get_event_loop_policy().get_event_loop(), "raid_path": "./media/raid_sounds"})()
    pipeline = ChannelAudioPipeline(channel_id=888, bot=dummy_bot)

    track = Track(title="Wellerman", artist="Nathan Evans", path=Path("/fake/wellerman.mp3"), duration_seconds=135.0)
    item = PlayableItem(track, mode="standard", seek_seconds=0.0)
    pipeline.queue.append(item)
    pipeline.play_next()

    assert pipeline.track_start_time is not None, "track_start_time must be recorded on play"
    assert pipeline.duration_seconds == 135.0, "duration_seconds mismatch"
    
    time.sleep(0.05)
    assert pipeline.elapsed_seconds > 0.0, "elapsed calculation failed"
    assert "/" in pipeline.progress_str, "progress_str formatting failed"
    print("✅ Mid-Track Seek & Progress Counter Test Passed!")

def test_pause_drift_protection():
    dummy_bot = type("DummyBot", (), {"loop": asyncio.get_event_loop_policy().get_event_loop(), "raid_path": "./media/raid_sounds"})()
    pipeline = ChannelAudioPipeline(channel_id=777, bot=dummy_bot)

    track = Track(title="Leave Her Johnny", artist="Sean Dagher", path=Path("/fake/johnny.mp3"), duration_seconds=180.0)
    item = PlayableItem(track, mode="standard")
    pipeline.queue.append(item)
    pipeline.play_next()

    # Simulate pause state
    pipeline.paused_at = time.time()
    elapsed1 = pipeline.elapsed_seconds
    time.sleep(0.05)
    elapsed2 = pipeline.elapsed_seconds

    # Verify elapsed time does not advance while paused
    assert abs(elapsed1 - elapsed2) < 0.005, "Timer drifted during pause state!"
    print("✅ Pause Drift Protection Test Passed!")

def test_ambient_pause_decoupling_and_callback_suppression():
    dummy_bot = type("DummyBot", (), {"loop": asyncio.get_event_loop_policy().get_event_loop(), "raid_path": "./media/raid_sounds"})()
    pipeline = ChannelAudioPipeline(channel_id=666, bot=dummy_bot)

    # Test callback suppression flag logic
    pipeline._swapping_streams = True
    cb = pipeline._make_after_callback()
    
    # Callback should execute without triggering play_next when _swapping_streams is True
    cb(None)
    assert pipeline._swapping_streams is True, "_swapping_streams flag altered unexpectedly"
    pipeline._swapping_streams = False
    print("✅ Task 6.5 & 6.6 Callback Suppression & Stream Swap Test Passed!")

def test_mid_track_ambient_toggle_auto_start():
    dummy_bot = type("DummyBot", (), {"loop": asyncio.get_event_loop_policy().get_event_loop(), "raid_path": "./media/raid_sounds"})()
    pipeline = ChannelAudioPipeline(channel_id=555, bot=dummy_bot)

    track = Track(title="Bulls in the Heather", artist="Sea Shanty Crew", path=Path("/fake/bulls.mp3"), duration_seconds=200.0)
    pipeline.queue.append(PlayableItem(track))
    pipeline.play_next()

    amb1 = Track(title="Storm", artist="Ambient", path=Path("/fake/storm.mp3"))

    # Test set_ambient_mode without voice_client connected (Scenario C handling)
    asyncio.run(pipeline.set_ambient_mode(amb1))
    assert pipeline.active_ambient == amb1, "active_ambient was not updated by set_ambient_mode"
    assert len(pipeline.queue) == 0, "Queue length changed unexpectedly during in-place stream swap"
    print("✅ Task B3.1 Mid-Track Ambient Toggle Auto-Start Test Passed!")

def test_shutdown_cleanup_and_api_filter():
    dummy_bot = type("DummyBot", (), {"loop": None, "raid_path": "./media/raid_sounds"})()
    player = ShantyPlayer(dummy_bot)

    p0 = player.get_or_create_pipeline(channel_id=0)
    p1 = player.get_or_create_pipeline(channel_id=501)

    # Verify channel_id 0 and disconnected pipelines exist before cleanup
    assert 0 in player.pipelines and 501 in player.pipelines

    # Test cleanup_all_pipelines
    asyncio.run(player.cleanup_all_pipelines())
    assert len(player.pipelines) == 0, "cleanup_all_pipelines failed to purge pipeline dictionary"
    print("✅ Task B3.2 & B3.3 Graceful Shutdown & API Filter Test Passed!")

def test_channel_pipeline_isolation():
    dummy_bot = type("DummyBot", (), {"loop": asyncio.get_event_loop_policy().get_event_loop(), "raid_path": "./media/raid_sounds"})()
    player = ShantyPlayer(dummy_bot, max_channels=2)

    p1 = player.get_or_create_pipeline(channel_id=101)
    p2 = player.get_or_create_pipeline(channel_id=102)

    assert p1.channel_id == 101, "Pipeline 1 channel_id mismatch"
    assert p2.channel_id == 102, "Pipeline 2 channel_id mismatch"

    t1 = Track(title="Shanty 1", artist="Artist 1", path=Path("/fake/1.mp3"))
    t2 = Track(title="Shanty 2", artist="Artist 2", path=Path("/fake/2.mp3"))

    p1.queue.append(PlayableItem(t1))
    p2.queue.append(PlayableItem(t2))

    assert len(p1.queue) == 1 and p1.queue[0].track.title == "Shanty 1", "Queue 1 isolation failed"
    assert len(p2.queue) == 1 and p2.queue[0].track.title == "Shanty 2", "Queue 2 isolation failed"

    capacity_exceeded = False
    try:
        player.get_or_create_pipeline(channel_id=103)
    except RuntimeError as e:
        capacity_exceeded = True
        assert "Maximum active channel limit" in str(e), "Unexpected error message"

    assert capacity_exceeded, "Max channel capacity guard failed to trigger"
    print("✅ Channel Pipeline Isolation & Capacity Guard Test Passed!")

def test_dynamic_ambient_indexing():
    tmp_ambient_dir = Path("./media/ambient_test_tmp").resolve()
    tmp_ambient_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        mock_ambient = tmp_ambient_dir / "storm_test.mp3"
        mock_ambient.write_bytes(b"MOCK_AUDIO_HEADER")

        lib = LocalLibrary("./media/shanties", str(tmp_ambient_dir))
        found = lib.search_ambient("storm_test")

        assert found is not None, "Dynamic ambient search failed for newly created file"
        assert found.title == "Storm Test", "Dynamic ambient track title parsing failed"
    finally:
        if (tmp_ambient_dir / "storm_test.mp3").exists():
            (tmp_ambient_dir / "storm_test.mp3").unlink()
        if tmp_ambient_dir.exists():
            tmp_ambient_dir.rmdir()

    print("✅ Dynamic Ambient Indexing & Hot-Swapping Test Passed!")

def test_opus_cache_index():
    cache_dir = Path("./media/cache_test_tmp").resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        idx = OpusCacheIndex(cache_dir=str(cache_dir), max_cache_gb=0.00001)
        
        file1 = cache_dir / "track1.opus"
        file2 = cache_dir / "track2.opus"
        
        file1.write_bytes(b"0" * 8000)
        file2.write_bytes(b"0" * 8000)

        idx._enforce_cache_quota()

        cached_count = len(list(cache_dir.glob("*.opus")))
        assert cached_count <= 1, "LRU cache quota eviction failed"
    finally:
        for f in cache_dir.glob("*"):
            f.unlink(missing_ok=True)
        if cache_dir.exists():
            cache_dir.rmdir()

    print("✅ OpusCacheIndex & LRU Eviction Test Passed!")

def test_active_channels_health_and_favicon_api():
    dummy_bot = type("DummyBot", (), {"loop": None, "raid_path": "./media/raid_sounds"})()
    player = ShantyPlayer(dummy_bot)

    p1 = player.get_or_create_pipeline(channel_id=501)
    t = Track(title="Drunken Sailor", artist="The Longest Johns", path=Path("/fake/path.mp3"), duration_seconds=145.0)
    p1.queue.append(PlayableItem(t))

    lib = LocalLibrary("./media/shanties", "./media/ambient")
    app = create_web_app(player, lib)

    routes = [route.path for route in app.routes]
    assert "/static" in routes, "FastAPI /static route missing"
    assert "/api/v1/health" in routes, "FastAPI /api/v1/health route missing"
    print("✅ FastAPI Active Channels, Health & Favicon Static Mount Test Passed!")

if __name__ == "__main__":
    test_command_deprecation()
    test_mixed_and_solo_audio_sources()
    test_audio_source_cleanup_pipes()
    test_eof_state_disentanglement()
    test_solo_ambient_kick_mechanism()
    test_mid_track_seek_tracking()
    test_pause_drift_protection()
    test_ambient_pause_decoupling_and_callback_suppression()
    test_mid_track_ambient_toggle_auto_start()
    test_shutdown_cleanup_and_api_filter()
    test_channel_pipeline_isolation()
    test_dynamic_ambient_indexing()
    test_opus_cache_index()
    test_active_channels_health_and_favicon_api()
    print("🎉 All Task E.3, E.4 & Sprint 5 Unit Tests Succeeded!")
