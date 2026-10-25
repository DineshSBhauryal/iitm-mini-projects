from __future__ import annotations

from typing import Any


class EvaluationOrchestrator:
    """Controls the full supplier evaluation workflow."""

    def __init__(self, document_tool: Any | None = None, validation_tool: Any | None = None, ranking_tool: Any | None = None):
        self.document_tool = document_tool
        self.validation_tool = validation_tool
        self.ranking_tool = ranking_tool

    def run(self, supplier_name: str, pdf_text: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Execute the evaluation workflow for one supplier."""
        result = {
            "supplier_name": supplier_name,
            "submission_date": metadata.get("submission_date"),
            "experience_rating": metadata.get("experience_rating", 0),
            "criteria": [],
            "risks": [],
            "overall_summary": "",
        }

        if self.validation_tool:
            result = self.validation_tool.normalize_result(result)

        if self.ranking_tool:
            result["absolute_score"] = self.ranking_tool.calculate_absolute_score(result)

        return result
