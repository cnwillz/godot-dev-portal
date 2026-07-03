"""
ci_runner.py — 调用 godot-docker-ci 镜像执行自动化测试。

流程：
1. 启动 Docker 容器（挂载项目目录到 /project）
2. 捕获 stdout/stderr 作为日志行
3. 容器退出后解析 JSON 输出
4. 将报告存入数据库
"""
from __future__ import annotations
import json
import os
import re
import time
from pathlib import Path
from typing import AsyncGenerator, Optional

import docker
from docker.errors import DockerException, NotFound

from config import settings
from models import Iteration, Project, Report, ReportType


class CiRunner:
    """Manages a single test run for a project iteration."""

    def __init__(self, project: Project, iteration: Iteration):
        self.project = project
        self.iteration = iteration
        self.container_id: Optional[str] = None
        self._client: Optional[docker.DockerClient] = None

    # ── Public API ──────────────────────────────────────────────────────

    async def stream_logs(self) -> AsyncGenerator[dict, None]:
        """
        Run the container and yield log events as dicts:

          {"type": "log", "line": "...", "timestamp": ...}
          {"type": "complete", "passed": True, "report_id": 1, "summary": {...}}
          {"type": "error", "message": "..."}
        """
        client = self._get_client()
        project_path = Path(self.project.godot_project_path)
        if not project_path.is_dir():
            yield {"type": "error", "message": f"Project path not found: {project_path}"}
            return

        cmd = [
            "node", "/godot-ci/godot-ci.js",
            "-g", "/usr/local/bin/godot",
            "-p", "/project",
            "--json",
        ]
        if self.project.godot_scene:
            cmd.extend(["-s", self.project.godot_scene])

        env = {}
        if settings.vision_api_key:
            env["VISION_API_KEY"] = settings.vision_api_key

        try:
            container = client.containers.run(
                image=settings.godot_ci_image,
                command=cmd,
                working_dir="/project",
                volumes={str(project_path.resolve()): {"bind": "/project", "mode": "rw"}},
                environment=env,
                detach=True,
                auto_remove=False,
                mem_limit="2g",
            )
            self.container_id = container.id

            # Stream logs
            raw_log = ""
            for log_line in container.logs(stream=True, follow=True):
                line = log_line.decode("utf-8", errors="replace").rstrip("\n")
                raw_log += line + "\n"
                yield {"type": "log", "line": line, "timestamp": time.time()}

            # Wait for exit
            result = container.wait(timeout=300)
            exit_code = result.get("StatusCode", 1)
            passed = exit_code == 0

            # Parse JSON output from logs
            summary = self._parse_json_output(raw_log)

            # Copy screenshots & reports from container
            report_dir = self._collect_artifacts(container, project_path, raw_log)

            # Store in DB
            report_id = self._store_report(passed, summary, report_dir, raw_log)

            yield {
                "type": "complete",
                "passed": passed,
                "report_id": report_id,
                "summary": summary,
                "exit_code": exit_code,
            }

        except DockerException as e:
            yield {"type": "error", "message": f"Docker error: {e}"}
        except Exception as e:
            yield {"type": "error", "message": f"Unexpected error: {e}"}
        finally:
            self._cleanup()

    # ── Internal ────────────────────────────────────────────────────────

    def _get_client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def _parse_json_output(self, raw_log: str) -> dict:
        """Try to find JSON output in the logs (from --json flag)."""
        import re
        # Look for a complete JSON object — the CLI outputs it at the end
        # Try matching with regex for a top-level JSON object
        json_match = re.search(r'\{[^{}]*"passed"[^{}]*\}', raw_log, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Try a more aggressive search — find the last block that looks like JSON
        lines = raw_log.splitlines()
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue

        # Fallback: parse stage indicators from text output
        summary = {"passed": False, "stages": {}, "artifacts": {}}
        stages_found = re.findall(r"(unit|snap|vision|seq):([✅❌])", raw_log)
        for stage, icon in stages_found:
            summary["stages"][stage] = icon == "✅"
        # Also check for overall pass/fail
        if re.search(r"✅ PASS\s+\(", raw_log):
            summary["passed"] = True
        return summary

    def _collect_artifacts(self, container, project_path: Path, raw_log: str) -> Optional[Path]:
        """Copy report files from container to local data directory."""
        report_dir = settings.reports_path / f"run_{int(time.time())}"
        os.makedirs(report_dir, exist_ok=True)

        try:
            # Try to copy reports directory from container
            # The container outputs to /project/reports/ci-*/
            bits, _ = container.get_archive("/project/reports")
            import tarfile
            import io
            tar_stream = io.BytesIO()
            for chunk in bits:
                tar_stream.write(chunk)
            tar_stream.seek(0)
            with tarfile.open(fileobj=tar_stream) as tar:
                tar.extractall(path=str(report_dir))
        except (NotFound, DockerException):
            # No reports in container — that's OK, some CI runs may have no output
            pass

        return report_dir if report_dir.exists() and any(report_dir.iterdir()) else None

    def _store_report(self, passed: bool, summary: dict, report_dir: Optional[Path], raw_log: str) -> int:
        """Create Report records from test results."""
        from database import SessionLocal
        db = SessionLocal()
        try:
            stages = summary.get("stages", {})
            # Create individual stage reports if available
            for stage_name, stage_passed in stages.items():
                if isinstance(stage_passed, bool):
                    try:
                        report_type = ReportType(stage_name)
                    except ValueError:
                        continue
                    report = Report(
                        iteration_id=self.iteration.id,
                        type=report_type,
                        passed=stage_passed,
                        details=json.dumps(stages.get(stage_name, {})),
                        screenshots_path=str(report_dir) if report_dir else "",
                    )
                    db.add(report)

            # Also create a synthetic "full" report
            all_pass = all(
                v for v in stages.values() if isinstance(v, bool)
            ) if stages else passed
            report = Report(
                iteration_id=self.iteration.id,
                type=ReportType.unit,  # "full" — reuse unit type as umbrella
                passed=all_pass,
                details=json.dumps(summary),
                screenshots_path=str(report_dir) if report_dir else "",
            )
            db.add(report)
            db.commit()
            db.refresh(report)
            return report.id
        finally:
            db.close()

    def _cleanup(self):
        """Remove the container if it still exists."""
        if self.container_id:
            try:
                client = self._get_client()
                c = client.containers.get(self.container_id)
                c.remove(force=True)
            except (NotFound, DockerException):
                pass
            self.container_id = None

    def stop(self):
        """Stop a running test."""
        if self.container_id:
            try:
                client = self._get_client()
                c = client.containers.get(self.container_id)
                c.kill()
            except (NotFound, DockerException):
                pass
