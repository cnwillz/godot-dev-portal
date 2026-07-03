"""
routers/preview.py — 游戏预览：启动/停止/状态/嵌入页面。
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from models import Project
from services.preview_manager import preview_manager

router = APIRouter(prefix="/projects/{project_id}/preview", tags=["preview"])

# Injected by main.py
render_template = None  # type: ignore


def _render(name: str, ctx: dict, request: Request) -> HTMLResponse:
    return render_template(name, ctx, request)


def _get_project(db: Session, project_id: int):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ── Preview page (embedded noVNC iframe) ─────────────────────────────────


@router.get("", response_class=HTMLResponse)
async def preview_page(request: Request, project_id: int, db: Session = Depends(get_db)):
    project = _get_project(db, project_id)
    status = await preview_manager.status(project_id)
    return _render("preview.html", {
        "project": project,
        "preview": status,
    }, request)


# ── Start preview ────────────────────────────────────────────────────────


@router.post("/start")
async def start_preview(project_id: int, db: Session = Depends(get_db)):
    project = _get_project(db, project_id)
    result = await preview_manager.start(
        project_id=project_id,
        godot_path=project.godot_project_path,
        scene=project.godot_scene,
    )
    if "error" in result:
        return JSONResponse({"error": result["error"]}, status_code=500)
    return result


# ── Stop preview ─────────────────────────────────────────────────────────


@router.post("/stop")
async def stop_preview(project_id: int, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    result = await preview_manager.stop(project_id)
    return result


# ── Status (JSON) ────────────────────────────────────────────────────────


@router.get("/status")
async def preview_status(project_id: int, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    return await preview_manager.status(project_id)
