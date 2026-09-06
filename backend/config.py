"""统一读取应用配置。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """应用配置模型，字段从环境变量 / backend/.env 读取。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8003
    cors_origins: str = "http://localhost:5175"

    storage_dir: str = str(BACKEND_DIR / "storage")
    ffprobe_path: str = "ffprobe"

    max_audio_bytes: int = 5 * 1024 * 1024
    min_audio_duration_s: float = 1.0
    max_audio_duration_s: float = 60.0
    audio_ttl_hours: int = 24
    upload_timeout_s: float = 5.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
