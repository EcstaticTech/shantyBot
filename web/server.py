from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

def _get_item_display_name(item) -> str:
    """Helper to extract display name from PlayableItem or Track object."""
    track = getattr(item, "track", item)
    return getattr(track, "display_name", getattr(track, "title", "Unknown Track"))

def create_web_app(player):
    app = FastAPI(docs_url=None, redoc_url=None)

    @app.get("/api/status")
    async def get_status():
        return {
            "current_track": _get_item_display_name(player.current_track) if player.current_track else None,
            "queue_length": len(player.queue),
            "queue": [_get_item_display_name(item) for item in player.queue]
        }

    @app.get("/", response_class=HTMLResponse)
    async def index_page(request: Request):
        current_track_name = _get_item_display_name(player.current_track) if player.current_track else None
        queue_items = [_get_item_display_name(item) for item in player.queue]
        
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "current_track": current_track_name,
                "queue": queue_items
            }
        )
    return app
