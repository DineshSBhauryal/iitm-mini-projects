import sqlite3

import pytest

from database.db_manager import DatabaseManager


def test_database_explorer_lists_tables_and_columns(tmp_path):
    manager = DatabaseManager(tmp_path / "explorer.db")

    tables = manager.list_tables()
    criteria_table = next(table for table in tables if table["name"] == "evaluation_criteria")

    assert criteria_table["row_count"] > 0
    assert "name" in {column["name"] for column in criteria_table["columns"]}


def test_database_explorer_runs_select_and_with_queries(tmp_path):
    manager = DatabaseManager(tmp_path / "explorer.db")

    columns, rows, truncated = manager.query_readonly(
        "SELECT name, weight FROM evaluation_criteria ORDER BY criterion_id LIMIT 2"
    )
    assert columns == ["name", "weight"]
    assert len(rows) == 2
    assert truncated is False

    with_columns, with_rows, _ = manager.query_readonly(
        "WITH active AS (SELECT name FROM evaluation_criteria WHERE is_active = 1) SELECT * FROM active"
    )
    assert with_columns == ["name"]
    assert with_rows


def test_database_explorer_rejects_write_queries(tmp_path):
    manager = DatabaseManager(tmp_path / "explorer.db")

    with pytest.raises(ValueError, match="Only SELECT"):
        manager.query_readonly("DELETE FROM evaluation_criteria")

    with pytest.raises(sqlite3.DatabaseError):
        manager.query_readonly("WITH selected AS (SELECT 1) DELETE FROM evaluation_criteria")


def test_database_explorer_rejects_multiple_statements_and_caps_rows(tmp_path):
    manager = DatabaseManager(tmp_path / "explorer.db")

    with pytest.raises(sqlite3.ProgrammingError):
        manager.query_readonly("SELECT 1; SELECT 2")

    _, rows, truncated = manager.query_readonly("SELECT * FROM evaluation_criteria", max_rows=2)
    assert len(rows) == 2
    assert truncated is True
