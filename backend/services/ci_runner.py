"""
ci_runner.py — 通过 Hermes CLI 执行自动化测试。

不再直接调 Docker。改为调用：
  hermes chat -q "load godot-docker-ci; run tests for /project/..."

由 Hermes 自行管理容器生命周期，Portal 只捕获输出。
"""
from __future__ import annotations
import json
import time
from typing import AsyncGenerator

from config import settings
from models import Iteration, Project, Report, ReportType
from services.hermes_client import HermesClient


class CiRunner:
    """通过 Hermes 执行一次测试运行。"""

    def __init__(self, project: Project, iteration: Iteration):
        self.project = project
        self.iteration = iteration
        self._hermes = HermesClient()

    async def stream_logs(self) -> AsyncGenerator[dict, None]:
        """执行测试，逐行输出结果。"""

        # 构造 Hermes 提示词
        prompt = self._build_test_prompt()

        yield {"type": "log", "line": "🚀 Dispatching to Hermes...", "timestamp": time.time()}
        yield {"type": "log", "line": f"📁 Project: {self.project.godot_project_path}", "timestamp": time.time()}
        yield {"type": "log", "line": f"🎬 Scene: {self.project.godot_scene}", "timestamp": time.time()}

        env_args = ""
        if settings.vision_api_key:
            env_args = f"VISION_API_KEY={settings.vision_api_key}"

        full_output = ""

        async for event in self._hermes.execute(
            prompt=prompt,
            skills=["godot-docker-ci"],
            timeout=600,
        ):
            if event["type"] == "log":
                full_output += event["line"] + "\n"
            yield event

            if event["type"] == "complete":
                result = event.get("result", {})
                passed = result.get("passed", event.get("exit_code", 1) == 0)

                # 存报告
                report_id = self._store_report(passed, result, full_output)

                yield {
                    "type": "complete",
                    "passed": passed,
                    "report_id": report_id,
                    "summary": result,
                    "exit_code": event.get("exit_code", 1),
                }
                return

            if event["type"] == "error":
                yield {
                    "type": "complete",
                    "passed": False,
                    "report_id": None,
                    "summary": {"error": event["message"]},
                    "exit_code": 1,
                }
                return

    def _build_test_prompt(self) -> str:
        """构造传给 Hermes 的提示词。"""
        project_path = self.project.godot_project_path
        scene = self.project.godot_scene

        return (
            f"load godot-docker-ci skill; "
            f"run the full automated test pipeline for the Godot project at {project_path} "
            f"using scene {scene}. "
            f"Execute: unit tests, screenshot capture, visual validation, and interaction sequence. "
            f"Output the final JSON result so the portal can parse it. "
            f"Do NOT ask any questions — execute immediately."
        )

    def _store_report(self, passed: bool, result: dict, raw_output: str) -> int:
        """将测试结果存入数据库。"""
        from database import SessionLocal
        db = SessionLocal()
        try:
            stages = result.get("stages", {})
            for stage_name, stage_passed in stages.items():
                if isinstance(stage_passed, bool):
                    try:
                        report_type = ReportType(stage_name)
                    except ValueError:
                        continue
                    try:
                        stage_detail = json.dumps({stage_name: stage_passed})
                    except (TypeError, ValueError):
                        stage_detail = str(stage_passed)
                    report = Report(
                        iteration_id=self.iteration.id,
                        type=report_type,
                        passed=stage_passed,
                        details=stage_detail,
                    )
                    db.add(report)

            # 总报告
            try:
                details_json = json.dumps(result)
            except (TypeError, ValueError):
                details_json = str(result)

            report = Report(
                iteration_id=self.iteration.id,
                type=ReportType.unit,
                passed=passed,
                details=details_json,
                duration_sec=result.get("duration_sec", 0.0),
            )
            db.add(report)
            db.commit()
            db.refresh(report)
            return report.id
        finally:
            db.close()
