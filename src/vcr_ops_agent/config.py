"""配置管理 — 环境变量 + 默认值"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 2048
    temperature: float = 0.3
    use_llm: bool = True

    @classmethod
    def from_env(cls) -> Settings:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        use_llm = bool(api_key) and os.environ.get("VCR_OPS_FAKE_MODE", "").lower() != "true"
        return cls(
            anthropic_api_key=api_key,
            anthropic_base_url=os.environ.get("ANTHROPIC_BASE_URL", ""),
            model=os.environ.get("VCR_OPS_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=int(os.environ.get("VCR_OPS_MAX_TOKENS", "2048")),
            temperature=float(os.environ.get("VCR_OPS_TEMPERATURE", "0.3")),
            use_llm=use_llm,
        )


settings = Settings.from_env()
