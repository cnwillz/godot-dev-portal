from __future__ import annotations
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from models import Iteration, IterationStatus, Task, TaskStatus

router = APIRouter(prefix="/projects/{project_id}/iterations", tags=["iterations"])

# Injected by main.py at startup
render_template = None  # type: ignore


def _get_project_or_404(db: Session, project_id: int):
    from models import Project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ── Create iteration ──────────────────────────────────────────────────────


@router.post("/new")
async def create_iteration(
    project_id: int,
    name: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(db, project_id)
    iteration = Iteration(project_id=project.id, name=name, description=description)
    db.add(iteration)
    db.commit()
    return RedirectResponse(url=f"/projects/{project.id}", status_code=303)


# ── Update status ─────────────────────────────────────────────────────────


@router.post("/{iteration_id}/status")
async def update_iteration_status(
    project_id: int,
    iteration_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(db, project_id)
    iteration = db.query(Iteration).filter(
        Iteration.id == iteration_id, Iteration.project_id == project.id
    ).first()
    if not iteration:
        raise HTTPException(status_code=404, detail="Iteration not found")
    try:
        iteration.status = IterationStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    db.commit()
    return RedirectResponse(url=f"/projects/{project.id}", status_code=303)


# ── Tasks ──────────────────────────────────────────────────────────────────


@router.post("/{iteration_id}/tasks/new")
async def create_task(
    project_id: int,
    iteration_id: int,
    title: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    iteration = db.query(Iteration).filter(
        Iteration.id == iteration_id, Iteration.project_id == project_id
    ).first()
    if not iteration:
        raise HTTPException(status_code=404, detail="Iteration not found")
    max_order = db.query(Task).filter(Task.iteration_id == iteration.id).count()
    task = Task(
        iteration_id=iteration.id,
        title=title,
        description=description,
        order=max_order,
    )
    db.add(task)
    db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{iteration_id}/tasks/{task_id}/status")
async def update_task_status(
    project_id: int,
    iteration_id: int,
    task_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.iteration_id == iteration_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        task.status = TaskStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{iteration_id}/tasks/{task_id}/delete")
async def delete_task(
    project_id: int,
    iteration_id: int,
    task_id: int,
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.iteration_id == iteration_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)
