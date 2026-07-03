from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/portal.db"
    godot_ci_image: str = "godot-ci:latest"
    vision_api_key: str = ""
    data_dir: str = "./data"
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir).resolve()

    @property
    def reports_path(self) -> Path:
        return self.data_path / "reports"

    @property
    def logs_path(self) -> Path:
        return self.data_path / "logs"

    @property
    def db_path(self) -> Path:
        return self.data_path / "portal.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
