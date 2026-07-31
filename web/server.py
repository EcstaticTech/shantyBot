from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
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

    @app.get("/api/status")
    async def get_status():
        is_playing = bool(player.voice_client and player.voice_client.is_playing())
        current_track_name = _get_item_display_name(player.current_track) if player.current_track else "None"
        ambient_name = _get_item_display_name(player.active_ambient) if player.active_ambient else "Off"
        
        indexed_tracks = []
        if library:
            indexed_tracks = getattr(library, "cache", getattr(library, "music_cache", []))

        return JSONResponse(content={
            "current_track": current_track_name,
            "ambient_mode": ambient_name,
            "is_playing": is_playing,
            "queue_length": len(player.queue),
            "total_shanties_indexed": len(indexed_tracks)
        })

    @app.get("/", response_class=HTMLResponse)
    async def index_page():
        current_track_name = _get_item_display_name(player.current_track) if player.current_track else "No shanty playing"
        ambient_name = _get_item_display_name(player.active_ambient) if player.active_ambient else "Off"
        queue_items = [_get_item_display_name(item) for item in player.queue]
        
        indexed_tracks = []
        if library:
            indexed_tracks = getattr(library, "cache", getattr(library, "music_cache", []))
        manifest_items = [_get_item_display_name(t) for t in indexed_tracks]

        # 1. Pre-compute Queue HTML block outside f-string
        if queue_items:
            items_list = "".join([f'<li class="item"><span class="idx">#{i+1}</span> <span>{item}</span></li>' for i, item in enumerate(queue_items)])
            queue_html = f'<ul class="item-list">{items_list}</ul>'
        else:
            queue_html = '<p class="empty-state">The ship log is empty. Queue up a shanty!</p>'

        # 2. Pre-compute Manifest HTML block outside f-string
        if manifest_items:
            items_list = "".join([f'<li class="manifest-item"><span class="dot">⚓</span> <span>{item}</span></li>' for i, item in enumerate(manifest_items)])
            manifest_html = f'<ul class="item-list">{items_list}</ul>'
        else:
            manifest_html = '<p class="empty-state">No local tracks indexed in ship log.</p>'

        queue_count = len(queue_items)
        indexed_count = len(indexed_tracks)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>shantyBot | Tavern Status</title>
    <meta http-equiv="refresh" content="5">
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
            margin-bottom: 2rem;
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

        .card-label {{
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
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

        <div class="grid-status">
            <div class="card card-full">
                <div class="card-label">🎵 Now Playing</div>
                <div class="now-playing-title">{current_track_name}</div>
            </div>
            <div class="card">
                <div class="card-label">🍻 Ambient Mode</div>
                <div class="ambient-value">{ambient_name}</div>
            </div>
            <div class="card">
                <div class="card-label">📚 Shanties Indexed</div>
                <div class="ambient-value">{indexed_count} Tracks</div>
            </div>
        </div>

        <div class="card card-full" style="margin-bottom: 1.5rem;">
            <div class="card-label">📜 Up Next in Queue ({queue_count})</div>
            {queue_html}
        </div>

        <div class="card card-full">
            <div class="card-label">⚓ Ship's Manifest (Local Track Library)</div>
            <div class="manifest-scroll">
                {manifest_html}
            </div>
        </div>

        <div class="footer">
            shantyBot Async Audio Engine • Auto-refreshes every 5s
        </div>
    </div>
</body>
</html>"""
        return HTMLResponse(content=html_content)

    return app
