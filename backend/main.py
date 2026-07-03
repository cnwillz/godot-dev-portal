from __future__ import annotations
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import settings
from database import init_db

# ── 初始化目录和数据库 ────────────────────────────────────────────────────
os.makedirs(settings.data_path, exist_ok=True)
os.makedirs(settings.reports_path, exist_ok=True)
os.makedirs(settings.logs_path, exist_ok=True)
init_db()

# ── App ───────────────────────────────────────────────────────────────────
app = FastAPI(title="Godot Dev Portal", version="0.1.0")

# ── Static files ──────────────────────────────────────────────────────────
static_dir = Path(__file__).parent.parent / "frontend" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── Templates ────────────────────────────────────────────────────────────
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# ── Register routers ──────────────────────────────────────────────────────
from routers.projects import router as projects_router
from routers.iterations import router as iterations_router

app.include_router(projects_router)
app.include_router(iterations_router)


# ── Root redirect ─────────────────────────────────────────────────────────


@app.get("/")
async def root():
    return RedirectResponse(url="/projects")


# ── Make templates available to routers ───────────────────────────────────

def render_template(name: str, context: dict, request: Request):
    """Render a Jinja2 template and return an HTMLResponse."""
    return templates.TemplateResponse(name, {**context, "request": request})


# Inject render_template into router modules so they can use it
import routers.projects as rp
import routers.iterations as ri

rp.render_template = render_template
ri.render_template = render_template
