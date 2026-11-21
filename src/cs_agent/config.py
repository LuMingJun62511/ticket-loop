"""集中配置。

约定：路径与环境变量只在这里读，其他模块不要直接碰 os.environ。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Paths:
    root: Path = ROOT
    data: Path = ROOT / "data"
    raw: Path = ROOT / "data" / "raw"
    synthetic: Path = ROOT / "data" / "synthetic"
    private: Path = ROOT / "data" / "private"
    splits: Path = ROOT / "data" / "splits"
    eval_dir: Path = ROOT / "eval"
    golden: Path = ROOT / "eval" / "golden"
    reports: Path = ROOT / "eval" / "reports"
    models: Path = ROOT / "models"


@dataclass(frozen=True)
class Settings:
    labels: tuple[str, ...] = ("退款", "物流", "其他")
    seed: int = int(os.getenv("SEED", "42"))

    api_base: str = os.getenv("API_BASE", "https://api.deepseek.com")
    api_key: str = os.getenv("API_KEY", "")
    big_model: str = os.getenv("BIG_MODEL", "deepseek-chat")

    ollama_base: str = os.getenv("OLLAMA_BASE", "http://127.0.0.1:11434")
    small_model: str = os.getenv("SMALL_MODEL", "qwen3:0.6b")

    # P4 扫完阈值再填；0 表示未校准
    route_threshold: float = float(os.getenv("ROUTE_THRESHOLD") or 0.0)


PATHS = Paths()
SETTINGS = Settings()
