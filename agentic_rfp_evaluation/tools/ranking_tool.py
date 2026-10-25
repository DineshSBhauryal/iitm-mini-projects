from __future__ import annotations

from typing import Any


class RankingTool:
    """Calculates weighted scores, benchmarks, PPI, and deterministic tie-break rules."""

    _weights = {
        1: 30,
        2: 20,
        3: 20,
        4: 20,
        5: 10,
    }

    def calculate_absolute_score(self, supplier_result: dict[str, Any]) -> float:
        criteria = supplier_result.get("criteria", [])
        if not criteria:
            return 0.0

        total = 0.0
        for item in criteria:
            criterion_id = int(item.get("criterion_id", 0))
            score = float(item.get("score", 0))
            max_score = float(item.get("max_score", 10))
            weight = float(self._weights.get(criterion_id, 0))
            if max_score > 0:
                total += (score / max_score) * weight
        return round(total, 2)

    def _compute_benchmarks(self, supplier_results: list[dict[str, Any]]) -> dict[int, float]:
        benchmarks: dict[int, float] = {}
        for criterion_id in range(1, 6):
            values = []
            for supplier in supplier_results:
                criterion = next(
                    (item for item in supplier.get("criteria", []) if int(item.get("criterion_id", 0)) == criterion_id),
                    None,
                )
                if criterion:
                    values.append(float(criterion.get("score", 0)))
            benchmarks[criterion_id] = max(values) if values else 0.0
        return benchmarks

    def _relative_performance(self, criterion_score: float, benchmark_score: float) -> float:
        if benchmark_score <= 0:
            return 100.0
        return round((criterion_score / benchmark_score) * 100, 2)

    def calculate_ppi(self, supplier_result: dict[str, Any], benchmarks: dict[int, float]) -> float:
        total_weighted = 0.0
        total_weight = 0.0

        for item in supplier_result.get("criteria", []):
            criterion_id = int(item.get("criterion_id", 0))
            criterion_weight = float(self._weights.get(criterion_id, 0))
            score = float(item.get("score", 0))
            max_score = float(item.get("max_score", 10))
            benchmark = float(benchmarks.get(criterion_id, 0))
            if criterion_weight <= 0:
                continue
            total_weight += criterion_weight
            if benchmark > 0:
                relative_pct = self._relative_performance(score / max_score * 100, benchmark / 10 * 100)
            else:
                relative_pct = 100.0
            total_weighted += relative_pct * criterion_weight

        ppi = (total_weighted / total_weight) if total_weight > 0 else 0.0
        return round(ppi, 2)

    def sort_by_tie_break(self, suppliers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            suppliers,
            key=lambda item: (
                -float(item.get("ppi", 0)),
                item.get("submission_date", "9999-12-31"),
                -float(item.get("experience_rating", 0)),
                item.get("supplier_name", ""),
            ),
        )

    def evaluate_run(self, supplier_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        benchmarks = self._compute_benchmarks(supplier_results)
        for supplier in supplier_results:
            supplier["absolute_score"] = self.calculate_absolute_score(supplier)
            supplier["ppi"] = self.calculate_ppi(supplier, benchmarks)
            supplier["benchmark_gap"] = {
                str(k): round(float(supplier.get("criteria", [{}])[0].get("score", 0)) if False else 0, 2)
                for k in range(1, 6)
            }

        ranked = self.sort_by_tie_break(supplier_results)
        for index, supplier in enumerate(ranked, start=1):
            supplier["final_rank"] = index
        return ranked
