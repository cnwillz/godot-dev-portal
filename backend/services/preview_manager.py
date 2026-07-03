"""
preview_manager.py — 管理 Godot 游戏预览 Docker 容器。

使用 godot-ci:latest 镜像启动 noVNC 容器，
在浏览器中可玩 Godot 游戏。
"""
from __future__ import annotations
import os
import socket
import time
from pathlib import Path
from typing import Optional

import docker
from docker.errors import DockerException, NotFound

from config import settings


# 端口范围
VNC_BASE_PORT = 5900
NOVNC_BASE_PORT = 8080
MAX_PREVIEWS = 10


class PreviewManager:
    """管理项目预览容器。"""

    def __init__(self):
        self._client: Optional[docker.DockerClient] = None
        # 内存中跟踪: {project_id: container_info}
        self._previews: dict[int, dict] = {}

    # ── Public API ──────────────────────────────────────────────────────

    async def start(self, project_id: int, godot_path: str, scene: str) -> dict:
        """启动预览容器，返回连接信息。"""
        existing = self._previews.get(project_id)
        if existing:
            # 检查容器是否还在运行
            try:
                c = self._get_client().containers.get(existing["container_id"])
                if c.status == "running":
                    return existing
                # 容器已停止，清理记录
                self._cleanup(project_id)
            except NotFound:
                self._cleanup(project_id)

        project_path = Path(godot_path)
        if not project_path.is_dir():
            return {"error": f"Project path not found: {godot_path}"}

        # 找空闲端口
        vnc_port = self._find_free_port(VNC_BASE_PORT)
        novnc_port = self._find_free_port(NOVNC_BASE_PORT)
        if not vnc_port or not novnc_port:
            return {"error": "No free ports available"}

        # 构建内联命令：跳过测试，直接启动游戏 + noVNC
        # 格式：Xvfb → Godot(游戏) → x11vnc → noVNC
        cmd = [
            "bash", "-c",
            'export DISPLAY=:99; '
            'Xvfb :99 -screen 0 1280x720x24 & '
            'sleep 1; '
            '/usr/local/bin/godot --editor --path /project --position 0,0 & '
            'sleep 5; '
            'x11vnc -display :99 -forever -shared -rfbport 5900 -nopw -quiet & '
            '/opt/noVNC/utils/novnc_proxy --vnc localhost:5900 --listen 8080 --web /opt/noVNC & '
            'echo "PREVIEW_READY"; '
            'wait'
        ]

        try:
            client = self._get_client()
            container = client.containers.run(
                image=settings.godot_ci_image,
                command=cmd,
                working_dir="/project",
                volumes={str(project_path.resolve()): {"bind": "/project", "mode": "rw"}},
                ports={
                    "5900/tcp": vnc_port,
                    "8080/tcp": novnc_port,
                },
                detach=True,
                auto_remove=True,
                mem_limit="2g",
            )

            info = {
                "project_id": project_id,
                "container_id": container.id,
                "vnc_port": vnc_port,
                "novnc_port": novnc_port,
                "url": f"http://localhost:{novnc_port}/vnc.html",
                "status": "starting",
                "started_at": time.time(),
            }
            self._previews[project_id] = info

            # 等待容器就绪
            for _ in range(30):
                try:
                    c = client.containers.get(container.id)
                    if c.status == "running":
                        # 检查 novnc 进程是否已在监听
                        if self._check_port(novnc_port):
                            info["status"] = "running"
                            break
                except NotFound:
                    break
                time.sleep(1)

            return info

        except DockerException as e:
            return {"error": f"Docker error: {e}"}

    async def stop(self, project_id: int) -> dict:
        """停止预览容器。"""
        info = self._previews.get(project_id)
        if not info:
            return {"status": "not_found", "message": "No preview running"}

        try:
            client = self._get_client()
            c = client.containers.get(info["container_id"])
            c.kill()
        except (NotFound, DockerException):
            pass

        self._cleanup(project_id)
        return {"status": "stopped"}

    async def status(self, project_id: int) -> dict:
        """获取预览状态。"""
        info = self._previews.get(project_id)
        if not info:
            return {"status": "stopped"}

        try:
            client = self._get_client()
            c = client.containers.get(info["container_id"])
            if c.status != "running":
                self._cleanup(project_id)
                return {"status": "stopped"}
            info["status"] = "running"
            return info
        except NotFound:
            self._cleanup(project_id)
            return {"status": "stopped"}

    # ── Internal ────────────────────────────────────────────────────────

    def _get_client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def _find_free_port(self, base: int) -> Optional[int]:
        """从 base 开始找第一个空闲端口。"""
        for port in range(base, base + MAX_PREVIEWS):
            if self._check_port(port):
                continue  # 已被占用
            return port
        return None

    @staticmethod
    def _check_port(port: int) -> bool:
        """检查端口是否已被占用。"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect(("127.0.0.1", port))
                return True
            except (ConnectionRefusedError, OSError):
                return False

    def _cleanup(self, project_id: int):
        """清理记录。"""
        self._previews.pop(project_id, None)

    def cleanup_all(self):
        """停止所有预览容器（服务关闭时调用）。"""
        for pid in list(self._previews.keys()):
            try:
                info = self._previews[pid]
                client = self._get_client()
                c = client.containers.get(info["container_id"])
                c.kill()
            except (NotFound, DockerException):
                pass
        self._previews.clear()


# 单例
preview_manager = PreviewManager()
