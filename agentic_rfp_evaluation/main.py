from __future__ import annotations

from config.settings import settings
from database.db_manager import DatabaseManager


def main() -> None:
    db = DatabaseManager(settings.database_path)
    criteria = db.get_active_criteria()

    print("Agentic RFP Evaluation project is initialized.")
    print(f"SQLite database: {settings.database_path}")
    print(f"Active criteria count: {len(criteria)}")
    for criterion in criteria:
        print(
            f"- {criterion['criterion_id']}: {criterion['name']} "
            f"({criterion['weight']}%, max {criterion['max_score']})"
        )


if __name__ == "__main__":
    main()
