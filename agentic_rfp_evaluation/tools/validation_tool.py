from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from models.scorecard import Scorecard


class ValidationTool:
    """Validates and normalizes LLM output against expected scorecard structure."""

    def __init__(self):
        self.warnings: list[str] = []

    def validate_result(self, payload: dict[str, Any]) -> tuple[bool, list[str]]:
        try:
            Scorecard(**payload)
            return True, []
        except ValidationError as exc:
            return False, [str(error) for error in exc.errors()]

    def normalize_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(payload)
        normalized_criteria: list[dict[str, Any]] = []

        for item in cleaned.get("criteria", []):
            criterion_id = int(item.get("criterion_id", 0))
            score = float(item.get("score", 0))
            max_score = max(float(item.get("max_score", 10)), 1.0)
            normalized_criteria.append(
                {
                    "criterion_id": criterion_id,
                    "score": max(0.0, min(score, 10.0)),
                    "max_score": max_score,
                    "justification": item.get("justification", "No explicit justification provided."),
                    "evidence": item.get("evidence", "No supporting evidence provided."),
                }
            )

        required_ids = [1, 2, 3, 4, 5]
        existing_ids = {int(item["criterion_id"]) for item in normalized_criteria}
        for criterion_id in required_ids:
            if criterion_id not in existing_ids:
                normalized_criteria.append(
                    {
                        "criterion_id": criterion_id,
                        "score": 0.0,
                        "max_score": 10.0,
                        "justification": "Missing criterion filled with a neutral score to preserve schema completeness.",
                        "evidence": "No evidence available in the supplier response.",
                    }
                )

        cleaned["criteria"] = sorted(normalized_criteria, key=lambda item: int(item["criterion_id"]))
        cleaned["risks"] = cleaned.get("risks", []) or ["No significant risks identified."]
        cleaned["overall_summary"] = cleaned.get("overall_summary", "") or "Proposal reviewed with available evidence."
        return cleaned
