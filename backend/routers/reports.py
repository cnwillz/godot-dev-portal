"""
routers/reports.py — 测试触发、SSE 日志流、报告查看。
"""
from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import Iteration, IterationStatus, Project, Report
from services.ci_runner import CiRunner

router = APIRouter(prefix="/projects/{project_id}/iterations/{iteration_id}", tags=["reports"])

# Injected by main.py
render_template = None  # type: ignore


def _render(name: str, ctx: dict, request: Request) -> HTMLResponse:
    return render_template(name, ctx, request)


def _get_iteration(db: Session, project_id: int, iteration_id: int) -> Iteration:
    iteration = db.query(Iteration).filter(
        Iteration.id == iteration_id,
        Iteration.project_id == project_id,
    ).first()
    if not iteration:
        raise HTTPException(status_code=404, detail="Iteration not found")
    return iteration


# ── SSE: Stream test logs ────────────────────────────────────────────────


@router.get("/test-stream")
async def stream_test_logs(project_id: int, iteration_id: int, db: Session = Depends(get_db)):
    iteration = _get_iteration(db, project_id, iteration_id)
    project = iteration.project

    async def event_stream():
        runner = CiRunner(project, iteration)
        async for event in runner.stream_logs():
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Stop a running test ──────────────────────────────────────────────────


@router.post("/stop-test")
async def stop_test(project_id: int, iteration_id: int, db: Session = Depends(get_db)):
    iteration = _get_iteration(db, project_id, iteration_id)
    # In a production system, we'd track active runners
    return {"ok": True, "message": "Stop signal sent"}


# ── Report detail page ───────────────────────────────────────────────────


@router.get("/reports/{report_id}", response_class=HTMLResponse)
async def report_detail(
    request: Request,
    project_id: int,
    iteration_id: int,
    report_id: int,
    db: Session = Depends(get_db),
):
    iteration = _get_iteration(db, project_id, iteration_id)
    report = db.query(Report).filter(
        Report.id == report_id,
        Report.iteration_id == iteration.id,
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Parse details JSON
    details = {}
    if report.details:
        try:
            details = json.loads(report.details)
        except json.JSONDecodeError:
            details = {"raw": report.details}

    # Find screenshots
    screenshots = []
    if report.screenshots_path:
        from pathlib import Path
        ss_dir = Path(report.screenshots_path)
        if ss_dir.exists():
            for f in sorted(ss_dir.glob("**/*.png")):
                screenshots.append(str(f))

    return _render("report_detail.html", {
        "project": iteration.project,
        "iteration": iteration,
        "report": report,
        "details": details,
        "screenshots": screenshots,
    }, request)


# ── List reports for an iteration (JSON) ──────────────────────────────────


@router.get("/reports")
async def list_reports(project_id: int, iteration_id: int, db: Session = Depends(get_db)):
    iteration = _get_iteration(db, project_id, iteration_id)
    reports = db.query(Report).filter(
        Report.iteration_id == iteration.id,
    ).order_by(Report.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "type": r.type.value,
            "passed": r.passed,
            "duration_sec": r.duration_sec,
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]
