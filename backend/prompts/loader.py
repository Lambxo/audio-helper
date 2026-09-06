"""读取单独维护的 DeepSeek 提示词文件。"""

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


@lru_cache
def load_extract_prompt() -> str:
    return (PROMPTS_DIR / "extract.txt").read_text(encoding="utf-8").strip()
