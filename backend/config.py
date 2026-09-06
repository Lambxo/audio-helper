"""统一读取应用配置。

本轮（项目骨架）只声明 /health 与跨域相关的最小配置项。
BAILIAN_API_KEY / DEEPSEEK_API_KEY / AMAP_API_KEY 等密钥已经写入
backend/.env.example 作为占位模板，但尚未在此声明为 Settings 字段，
会在实现对应接口（/asr、/extract、/search、/finalize）的轮次中补充，
避免本轮引入还用不到的配置字段。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置模型，字段从环境变量 / backend/.env 读取。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略 .env 中尚未声明为字段的其它占位变量
    )

    # 服务监听配置
    app_host: str = "0.0.0.0"
    app_port: int = 8003

    # 允许跨域访问的前端地址，多个用英文逗号分隔
    cors_origins: str = "http://localhost:5175"

    @property
    def cors_origin_list(self) -> list[str]:
        """将 cors_origins 拆分为列表，供 CORSMiddleware 使用。"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """缓存 Settings 实例，避免重复读取 .env。"""
    return Settings()


settings = get_settings()
