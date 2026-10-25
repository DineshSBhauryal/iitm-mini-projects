from __future__ import annotations

from config.settings import settings
from database.db_manager import DatabaseManager


def init_database() -> DatabaseManager:
    return DatabaseManager(settings.database_path)


if __name__ == "__main__":
    db = init_database()
    print(f"Database created at: {settings.database_path}")
    print(f"Active criteria: {db.get_active_criteria()}")
