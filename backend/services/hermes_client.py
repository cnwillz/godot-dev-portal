"""
hermes_client.py — 通过子进程调用外部 Hermes CLI。

Portal 不直接操作 Docker，而是向 Hermes Agent 发指令，
由 Hermes 加载对应 skill 执行任务。
"""
from __future__ import annotations
import asyncio
import json
import os
import re
from pathlib import Path
from typing import AsyncGenerator, Optional


# Hermes CLI 路径（macOS 上安装路径）
HERMES_PATH = os.path.expanduser("~/.local/bin/hermes")

# 后备路径
FALLBACK_PATHS = [
    "/usr/local/bin/hermes",
    "/usr/bin/hermes",
    os.path.expanduser("~/.local/bin/hermes"),
]


def _find_hermes() -> str:
    if os.path.exists(HERMES_PATH):
        return HERMES_PATH
    for p in FALLBACK_PATHS:
        if os.path.exists(p):
            return p
    return HERMES_PATH  # fallback even if not found, will fail gracefully


class HermesClient:
    """异步调用 Hermes CLI 执行任务。"""

    def __init__(self):
        self.hermes_path = _find_hermes()
        self._proc: Optional[asyncio.subprocess.Process] = None

    async def execute(
        self,
        prompt: str,
        *,
        skills: Optional[list[str]] = None,
        timeout: int = 600,
    ) -> AsyncGenerator[dict, None]:
        """
        执行一条 hermes chat -q 命令，逐行输出结果。

        Yields:
            {"type": "log", "line": "...", "timestamp": ...}
            {"type": "complete", "result": {...}}
            {"type": "error", "message": "..."}
        """
        skills_flag = ""
        if skills:
            skills_flag = f"--skills={','.join(skills)}"

        # --skills 是全局 flag，必须在 chat 之前
        cmd_parts = [self.hermes_path]
        if skills_flag:
            cmd_parts.append(skills_flag)
        cmd_parts.extend(["chat", "-q"])
        cmd_parts.append(prompt)

        import time
        import shlex

        cmd_str = " ".join(shlex.quote(p) for p in cmd_parts)
        yield {"type": "log", "line": f"$ {cmd_str}", "timestamp": time.time()}

        try:
            self._proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "TERM": "dumb", "FORCE_COLOR": "0"},
            )

            # 读取 stdout
            assert self._proc.stdout is not None
            full_output = ""
            while True:
                line_bytes = await self._proc.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
                # 去掉 ANSI 转义序列
                clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line)
                full_output += clean + "\n"
                yield {"type": "log", "line": clean, "timestamp": time.time()}

            # 读取剩余的 stderr
            assert self._proc.stderr is not None
            stderr_bytes = await self._proc.stderr.read()
            if stderr_bytes:
                stderr_text = stderr_bytes.decode("utf-8", errors="replace")
                clean_stderr = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', stderr_text)
                for line in clean_stderr.splitlines():
                    if line.strip():
                        yield {"type": "log", "line": f"[stderr] {line.strip()}", "timestamp": time.time()}

            exit_code = await self._proc.wait()

            # 尝试从输出中解析 JSON 结果
            result = self._parse_result(full_output, exit_code)

            yield {
                "type": "complete",
                "exit_code": exit_code,
                "result": result,
            }

        except asyncio.TimeoutError:
            yield {"type": "error", "message": f"Task timed out after {timeout}s"}
            self._kill()
        except FileNotFoundError:
            yield {
                "type": "error",
                "message": f"Hermes CLI not found at {self.hermes_path}. "
                          f"Install: curl -fsSL https://raw.githubusercontent.com/"
                          f"NousResearch/hermes-agent/main/scripts/install.sh | bash"
            }
        except Exception as e:
            yield {"type": "error", "message": f"Hermes execution error: {e}"}
            self._kill()
        finally:
            self._proc = None

    def _parse_result(self, output: str, exit_code: int) -> dict:
        """从 Hermes 输出中提取结构化结果。"""
        result = {
            "passed": exit_code == 0,
            "exit_code": exit_code,
            "output_preview": output[-500:] if len(output) > 500 else output,
            "stages": {},
        }

        # 解析阶段指示器 (unit✅ snap✅ vision⏭ etc.)
        stages = re.findall(r"(unit|snap|vision|seq)\s*[:：]?\s*([✅❌⏭✔✖])", output)
        for stage, icon in stages:
            result["stages"][stage] = icon in ("✅", "✔")

        # 检测整体通过/失败
        if re.search(r"(?:✅|✔)\s*(?:PASS|All tests|all passed)", output, re.IGNORECASE):
            result["passed"] = True
        elif re.search(r"(?:❌|✖)\s*(?:FAIL|failed|error)", output, re.IGNORECASE):
            result["passed"] = False

        return result

    def _kill(self):
        """强制终止子进程。"""
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.kill()
            except ProcessLookupError:
                pass
