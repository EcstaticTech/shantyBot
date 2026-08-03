from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from core.player import ShantyPlayer
from core.library import LocalLibrary

def _get_item_display_name(item) -> str:
    """Helper to extract display name from PlayableItem or Track object."""
    if not item:
        return "None"
    track = getattr(item, "track", item)
    return getattr(track, "display_name", getattr(track, "title", str(track)))

def create_web_app(player: ShantyPlayer, library: LocalLibrary | None = None) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None)
    static_dir = Path("web/static").resolve()
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/api/v1/health")
    async def get_health():
        """Exposes overall system health and channel pipeline progress status."""
        channels = []
        for channel_id, pipeline in player.pipelines.items():
            channels.append({
                "channel_id": channel_id,
                "is_playing": bool(pipeline.voice_client and pipeline.voice_client.is_playing()),
                "is_paused": pipeline.is_paused,
                "elapsed_seconds": round(pipeline.elapsed_seconds, 2),
                "duration_seconds": round(pipeline.duration_seconds, 2),
                "progress_str": pipeline.progress_str
            })
        return JSONResponse(content={
            "status": "healthy",
            "active_pipelines": len(player.pipelines),
            "channels": channels
        })

    @app.get("/api/v1/channels/active")
    async def get_active_channels():
        """Exposes status, playback progress, and active queues across all connected voice channel pipelines."""
        active = []
        for channel_id, pipeline in list(player.pipelines.items()):
            if channel_id <= 0:
                continue
            vc = pipeline.voice_client
            if not vc or not vc.is_connected():
                continue
            is_playing = bool(vc.is_playing() or vc.is_paused())
            channel_name = vc.channel.name if (hasattr(vc, "channel") and vc.channel) else f"Channel #{channel_id}"

            current_name = _get_item_display_name(pipeline.current_track) if pipeline.current_track else "No shanty playing"
            ambient_name = _get_item_display_name(pipeline.active_ambient) if pipeline.active_ambient else "Off"
            queue_names = [_get_item_display_name(item) for item in pipeline.queue]

            active.append({
                "channel_id": channel_id,
                "channel_name": channel_name,
                "is_playing": is_playing,
                "is_paused": pipeline.is_paused,
                "shuffle_mode": pipeline.shuffle_mode,
                "current_track": current_name,
                "ambient_mode": ambient_name,
                "elapsed_seconds": round(pipeline.elapsed_seconds, 2),
                "duration_seconds": round(pipeline.duration_seconds, 2),
                "progress_str": pipeline.progress_str,
                "queue_length": len(pipeline.queue),
                "queue": queue_names
            })

        indexed_tracks = []
        if library:
            indexed_tracks = getattr(library, "cache", getattr(library, "music_cache", []))

        return JSONResponse(content={
            "active_channels": active,
            "total_shanties_indexed": len(indexed_tracks)
        })

    @app.get("/api/status")
    async def get_status():
        """Backward compatibility endpoint returning primary pipeline status."""
        pipeline = player.primary_pipeline
        is_playing = bool(pipeline.voice_client and pipeline.voice_client.is_playing())
        current_track_name = _get_item_display_name(pipeline.current_track) if pipeline.current_track else "None"
        ambient_name = _get_item_display_name(pipeline.active_ambient) if pipeline.active_ambient else "Off"
        
        indexed_tracks = []
        if library:
            indexed_tracks = getattr(library, "cache", getattr(library, "music_cache", []))

        return JSONResponse(content={
            "current_track": current_track_name,
            "ambient_mode": ambient_name,
            "shuffle_mode": pipeline.shuffle_mode,
            "is_playing": is_playing,
            "is_paused": pipeline.is_paused,
            "elapsed_seconds": round(pipeline.elapsed_seconds, 2),
            "duration_seconds": round(pipeline.duration_seconds, 2),
            "progress_str": pipeline.progress_str,
            "queue_length": len(pipeline.queue),
            "total_shanties_indexed": len(indexed_tracks)
        })

    @app.get("/", response_class=HTMLResponse)
    async def index_page():
        indexed_tracks = []
        if library:
            indexed_tracks = getattr(library, "cache", getattr(library, "music_cache", []))
        manifest_items = [_get_item_display_name(t) for t in indexed_tracks]

        if manifest_items:
            items_list = "".join([f'<li class="manifest-item"><span class="dot">⚓</span> <span>{item}</span></li>' for item in manifest_items])
            manifest_html = f'<ul class="item-list">{items_list}</ul>'
        else:
            manifest_html = '<p class="empty-state">No local tracks indexed in ship log.</p>'

        indexed_count = len(indexed_tracks)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>shantyBot | Tavern Status</title>
    <link rel="apple-touch-icon" sizes="180x180" href="/static/favicons/apple-touch-icon.png">
    <link rel="icon" type="image/png" sizes="32x32" href="/static/favicons/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/static/favicons/favicon-16x16.png">
    <link rel="shortcut icon" href="/static/favicons/favicon.ico">
    <link rel="manifest" href="/static/favicons/site.webmanifest">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0b0e14;
            --bg-card: rgba(22, 28, 38, 0.85);
            --border-color: rgba(241, 196, 15, 0.25);
            --accent-gold: #f1c40f;
            --accent-copper: #e67e22;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --live-green: #2ecc71;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            background-image: 
                radial-gradient(at 0% 0%, rgba(230, 126, 34, 0.12) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(241, 196, 15, 0.08) 0px, transparent 50%);
            min-height: 100vh;
            color: var(--text-primary);
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 2rem 1rem;
        }}

        .container {{
            width: 100%;
            max-width: 720px;
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 2.5rem;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5), inset 0 1px 1px rgba(255, 255, 255, 0.1);
        }}

        .header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        .brand-icon {{
            font-size: 2rem;
        }}

        .brand-title {{
            font-size: 1.6rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-copper), var(--accent-gold));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .badge-live {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(46, 204, 113, 0.15);
            color: var(--live-green);
            padding: 0.35rem 0.85rem;
            border-radius: 50px;
            font-size: 0.85rem;
            font-weight: 600;
            border: 1px solid rgba(46, 204, 113, 0.3);
        }}

        .pulse-dot {{
            width: 8px;
            height: 8px;
            background: var(--live-green);
            border-radius: 50%;
            box-shadow: 0 0 0 0 rgba(46, 204, 113, 0.7);
            animation: pulse 1.6s infinite;
        }}

        @keyframes pulse {{
            0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(46, 204, 113, 0.7); }}
            70% {{ transform: scale(1); box-shadow: 0 0 0 6px rgba(46, 204, 113, 0); }}
            100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(46, 204, 113, 0); }}
        }}

        .channel-selector-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.5rem;
            background: rgba(15, 20, 28, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.05);
            padding: 0.85rem 1.25rem;
            border-radius: 12px;
        }}

        .select-label {{
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--text-secondary);
        }}

        .channel-select {{
            background: rgba(22, 28, 38, 0.95);
            color: var(--accent-gold);
            border: 1px solid var(--border-color);
            padding: 0.4rem 1rem;
            border-radius: 8px;
            font-family: inherit;
            font-size: 0.95rem;
            font-weight: 600;
            outline: none;
            cursor: pointer;
        }}

        .grid-status {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}

        .card {{
            background: rgba(15, 20, 28, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 14px;
            padding: 1.25rem;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}

        .card:hover {{
            border-color: var(--border-color);
            transform: translateY(-2px);
        }}

        .card-full {{
            grid-column: 1 / -1;
        }}

        .now-playing-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.5rem;
        }}

        .progress-timestamp {{
            font-size: 0.9rem;
            font-weight: 700;
            color: var(--accent-copper);
            letter-spacing: 0.05em;
            font-variant-numeric: tabular-nums;
        }}

        .card-label {{
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-secondary);
            font-weight: 600;
        }}

        .now-playing-title {{
            font-size: 1.2rem;
            font-weight: 600;
            color: var(--accent-gold);
            word-break: break-word;
        }}

        .ambient-value {{
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--accent-copper);
        }}

        .item-list {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
            margin-top: 0.75rem;
        }}

        .item {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            background: rgba(255, 255, 255, 0.03);
            padding: 0.75rem 1rem;
            border-radius: 10px;
            font-size: 0.95rem;
            color: var(--text-primary);
        }}

        .manifest-scroll {{
            max-height: 220px;
            overflow-y: auto;
            padding-right: 0.5rem;
        }}

        .manifest-scroll::-webkit-scrollbar {{
            width: 6px;
        }}
        .manifest-scroll::-webkit-scrollbar-thumb {{
            background: var(--border-color);
            border-radius: 4px;
        }}

        .manifest-item {{
            display: flex;
            align-items: center;
            gap: 0.6rem;
            padding: 0.5rem 0.75rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            font-size: 0.9rem;
            color: var(--text-primary);
        }}

        .idx {{
            color: var(--accent-copper);
            font-weight: 700;
            font-size: 0.85rem;
            min-width: 1.5rem;
        }}

        .dot {{
            font-size: 0.85rem;
        }}

        .empty-state {{
            color: var(--text-secondary);
            font-style: italic;
            font-size: 0.95rem;
        }}

        .footer {{
            text-align: center;
            margin-top: 2rem;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="brand">
                <span class="brand-icon">🏴‍☠️</span>
                <h1 class="brand-title">shantyBot Tavern</h1>
            </div>
            <div class="badge-live">
                <div class="pulse-dot"></div>
                LIVE
            </div>
        </div>

        <div class="channel-selector-row">
            <span class="select-label">🔊 Active Voice Channel</span>
            <select id="channelSelect" class="channel-select" onchange="renderSelectedChannel()">
                <option value="">Loading channels...</option>
            </select>
        </div>

        <div class="grid-status">
            <div class="card card-full">
                <div class="now-playing-header">
                    <span class="card-label">🎵 Now Playing</span>
                    <span id="progressCounter" class="progress-timestamp">00:00 / 00:00</span>
                </div>
                <div id="nowPlaying" class="now-playing-title">No active voice channels</div>
            </div>
            <div class="card">
                <div class="card-label">🍻 Ambient Mode</div>
                <div id="ambientMode" class="ambient-value">Off</div>
            </div>
            <div class="card">
                <div class="card-label">🔀 Shuffle Mode</div>
                <div id="shuffleMode" class="ambient-value">Off</div>
            </div>
            <div class="card">
                <div class="card-label">📚 Shanties Indexed</div>
                <div class="ambient-value">{indexed_count} Tracks</div>
            </div>
        </div>

        <div class="card card-full" style="margin-bottom: 1.5rem;">
            <div id="queueHeader" class="card-label">📜 Up Next in Queue (0)</div>
            <div id="queueContainer">
                <p class="empty-state">No active voice channels.</p>
            </div>
        </div>

        <div class="card card-full">
            <div class="card-label">⚓ Ship's Manifest (Local Track Library)</div>
            <div class="manifest-scroll">
                {manifest_html}
            </div>
        </div>

        <div class="footer">
            shantyBot Multi-Channel Audio Engine • Real-time status sync
        </div>
    </div>

    <script>
        let cachedChannels = [];

        async function fetchStatus() {{
            try {{
                const res = await fetch('/api/v1/channels/active');
                if (!res.ok) return;
                const data = await res.json();
                cachedChannels = data.active_channels || [];
                updateChannelDropdown();
                renderSelectedChannel();
            }} catch (e) {{
                console.error("Status fetch error:", e);
            }}
        }}

        function updateChannelDropdown() {{
            const select = document.getElementById('channelSelect');
            const selectedVal = select.value;
            
            if (cachedChannels.length === 0) {{
                select.innerHTML = '<option value="">No Active Channels</option>';
                return;
            }}

            let optionsHtml = '';
            cachedChannels.forEach((ch, idx) => {{
                optionsHtml += `<option value="${{ch.channel_id}}">${{ch.channel_name}}</option>`;
            }});

            select.innerHTML = optionsHtml;
            
            const exists = cachedChannels.some(ch => ch.channel_id.toString() === selectedVal);
            if (exists) {{
                select.value = selectedVal;
            }} else {{
                select.value = cachedChannels[0].channel_id.toString();
            }}
        }}

        function renderSelectedChannel() {{
            const select = document.getElementById('channelSelect');
            const selectedId = select.value;
            const nowPlayingEl = document.getElementById('nowPlaying');
            const progressCounterEl = document.getElementById('progressCounter');
            const ambientEl = document.getElementById('ambientMode');
            const shuffleEl = document.getElementById('shuffleMode');
            const queueHeaderEl = document.getElementById('queueHeader');
            const queueContainerEl = document.getElementById('queueContainer');

            if (!selectedId || cachedChannels.length === 0) {{
                nowPlayingEl.innerText = "No active voice channels";
                progressCounterEl.innerText = "00:00 / 00:00";
                ambientEl.innerText = "Off";
                if (shuffleEl) shuffleEl.innerText = "Off";
                queueHeaderEl.innerText = "📜 Up Next in Queue (0)";
                queueContainerEl.innerHTML = '<p class="empty-state">No active voice channels.</p>';
                return;
            }}

            const ch = cachedChannels.find(c => c.channel_id.toString() === selectedId);
            if (!ch) return;

            nowPlayingEl.innerText = ch.current_track;
            progressCounterEl.innerText = ch.progress_str || "00:00 / 00:00";
            ambientEl.innerText = ch.ambient_mode;
            if (shuffleEl) shuffleEl.innerText = ch.shuffle_mode ? "On" : "Off";
            queueHeaderEl.innerText = `📜 Up Next in Queue (${{ch.queue_length}})`;

            if (ch.queue && ch.queue.length > 0) {{
                const itemsList = ch.queue.map((item, idx) => 
                    `<li class="item"><span class="idx">#${{idx + 1}}</span> <span>${{item}}</span></li>`
                ).join('');
                queueContainerEl.innerHTML = `<ul class="item-list">${{itemsList}}</ul>`;
            }} else {{
                queueContainerEl.innerHTML = '<p class="empty-state">The queue is empty for this channel.</p>';
            }}
        }}

        fetchStatus();
        setInterval(fetchStatus, 1000);
    </script>
</body>
</html>"""
        return HTMLResponse(content=html_content)

    return app
