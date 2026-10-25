from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppSettings:
    project_root: Path = Path(__file__).resolve().parent.parent
    database_path: Path = project_root / "data" / "rfp_evaluation.db"
    upload_dir: Path = project_root / "uploads"
    output_dir: Path = project_root / "output"
    sample_criteria: list[dict[str, float | str]] = None

    def __post_init__(self):
        if self.sample_criteria is None:
            self.sample_criteria = [
                {"name": "Technical Capability", "weight": 30, "max_score": 10},
                {"name": "Implementation Plan", "weight": 20, "max_score": 10},
                {"name": "Commercial Value", "weight": 20, "max_score": 10},
                {"name": "Security & Compliance", "weight": 20, "max_score": 10},
                {"name": "Support & Experience", "weight": 10, "max_score": 10},
            ]

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


settings = AppSettings()
