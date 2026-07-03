from __future__ import annotations
import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ────────────────────────────────────────────────────────────────


class IterationStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    done = "done"


class TaskStatus(str, enum.Enum):
    todo = "todo"
    doing = "doing"
    done = "done"


class ReportType(str, enum.Enum):
    unit = "unit"
    snap = "snap"
    vision = "vision"
    seq = "seq"


# ── Models ───────────────────────────────────────────────────────────────


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default="")
    godot_project_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    godot_scene: Mapped[str] = mapped_column(String(255), default="res://scenes/game.tscn")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    iterations: Mapped[list[Iteration]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Iteration.created_at.desc()"
    )

    @property
    def active_iteration(self) -> Optional[Iteration]:
        for i in self.iterations:
            if i.status == IterationStatus.active:
                return i
        return None


class Iteration(Base):
    __tablename__ = "iterations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default="")
    status: Mapped[IterationStatus] = mapped_column(
        Enum(IterationStatus), default=IterationStatus.draft, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    project: Mapped[Project] = relationship(back_populates="iterations")
    tasks: Mapped[list[Task]] = relationship(
        back_populates="iteration", cascade="all, delete-orphan", order_by="Task.order"
    )
    reports: Mapped[list[Report]] = relationship(
        back_populates="iteration", cascade="all, delete-orphan", order_by="Report.created_at.desc()"
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    iteration_id: Mapped[int] = mapped_column(Integer, ForeignKey("iterations.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default="")
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.todo, nullable=False
    )
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    iteration: Mapped[Iteration] = relationship(back_populates="tasks")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    iteration_id: Mapped[int] = mapped_column(Integer, ForeignKey("iterations.id"), nullable=False)
    type: Mapped[ReportType] = mapped_column(Enum(ReportType), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[Optional[str]] = mapped_column(Text, default="")  # JSON summary
    screenshots_path: Mapped[Optional[str]] = mapped_column(String(1024), default="")
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    iteration: Mapped[Iteration] = relationship(back_populates="reports")
