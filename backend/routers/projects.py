from __future__ import annotations
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import Project

router = APIRouter(prefix="/projects", tags=["projects"])

# Injected by main.py at startup
render_template = None  # type: ignore


def _render(name: str, ctx: dict, request: Request) -> HTMLResponse:
    return render_template(name, ctx, request)


# ── List ─────────────────────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
async def list_projects(request: Request, db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.updated_at.desc()).all()
    return _render("projects_list.html", {"projects": projects}, request)


# ── Detail ────────────────────────────────────────────────────────────────


@router.get("/{project_id}", response_class=HTMLResponse)
async def project_detail(request: Request, project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _render("project_detail.html", {"project": project}, request)


# ── Create form ──────────────────────────────────────────────────────────


@router.get("/new", response_class=HTMLResponse)
async def new_project_form(request: Request):
    return _render("project_form.html", {"project": None}, request)


@router.post("/new")
async def create_project(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    godot_project_path: str = Form(...),
    godot_scene: str = Form("res://scenes/game.tscn"),
    db: Session = Depends(get_db),
):
    project = Project(
        name=name,
        description=description,
        godot_project_path=godot_project_path,
        godot_scene=godot_scene,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return RedirectResponse(url=f"/projects/{project.id}", status_code=303)


# ── Edit form ────────────────────────────────────────────────────────────


@router.get("/{project_id}/edit", response_class=HTMLResponse)
async def edit_project_form(request: Request, project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _render("project_form.html", {"project": project}, request)


@router.post("/{project_id}/edit")
async def update_project(
    request: Request,
    project_id: int,
    name: str = Form(...),
    description: str = Form(""),
    godot_project_path: str = Form(...),
    godot_scene: str = Form("res://scenes/game.tscn"),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.name = name
    project.description = description
    project.godot_project_path = godot_project_path
    project.godot_scene = godot_scene
    db.commit()
    return RedirectResponse(url=f"/projects/{project.id}", status_code=303)


# ── Delete ───────────────────────────────────────────────────────────────


@router.post("/{project_id}/delete")
async def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return RedirectResponse(url="/projects", status_code=303)
