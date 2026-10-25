from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


class DatabaseManager:
    """Handles SQLite setup, criteria loading, and result persistence."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _connect_readonly(self) -> sqlite3.Connection:
        database_uri = f"{self.db_path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(database_uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def list_tables(self) -> list[dict[str, Any]]:
        with closing(self._connect_readonly()) as conn:
            self._load_sqlite_vec(conn)
            rows = conn.execute(
                """
                SELECT name, sql
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name COLLATE NOCASE
                """
            ).fetchall()
            tables = []
            for row in rows:
                table = dict(row)
                table_name = table["name"].replace('"', '""')
                table["columns"] = [
                    dict(column)
                    for column in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
                ]
                table["row_count"] = int(
                    conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
                )
                tables.append(table)
            return tables

    def query_readonly(self, sql: str, max_rows: int = 1000) -> tuple[list[str], list[dict[str, Any]], bool]:
        statement = sql.strip()
        if not statement:
            raise ValueError("Enter a SELECT query to run.")
        if not statement.lower().startswith(("select", "with")):
            raise ValueError("Only SELECT queries and read-only WITH queries are allowed.")

        allowed_actions = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
            getattr(sqlite3, "SQLITE_RECURSIVE", -1),
        }

        def authorize(action: int, arg1: str | None, arg2: str | None, database: str | None, trigger: str | None) -> int:
            if action not in allowed_actions:
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_FUNCTION and (arg2 or arg1 or "").lower() == "load_extension":
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        with closing(self._connect_readonly()) as conn:
            self._load_sqlite_vec(conn)
            conn.set_authorizer(authorize)
            conn.set_progress_handler(lambda: 1, 1_000_000)
            cursor = conn.execute(statement)
            if cursor.description is None:
                raise ValueError("The query did not return a result set.")
            columns = [description[0] for description in cursor.description]
            rows = [dict(row) for row in cursor.fetchmany(max_rows + 1)]
            truncated = len(rows) > max_rows
            return columns, rows[:max_rows], truncated

    def initialize(self) -> None:
        schema_path = Path(__file__).resolve().parent / "schema.sql"
        schema_sql = schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(schema_sql)
            existing_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(proposal_chunks)").fetchall()
            }
            metadata_columns = {
                "page_start": "INTEGER",
                "page_end": "INTEGER",
                "heading": "TEXT",
                "section_path_json": "TEXT",
                "boundary_type": "TEXT",
                "embedding_text": "TEXT",
            }
            for column_name, column_type in metadata_columns.items():
                if column_name not in existing_columns:
                    conn.execute(f'ALTER TABLE proposal_chunks ADD COLUMN "{column_name}" {column_type}')
            conn.commit()
        self.seed_default_criteria()

    def seed_default_criteria(self) -> None:
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM evaluation_criteria").fetchone()[0]
            if count > 0:
                return

            default_criteria = [
                (
                    1,
                    "Technical Capability",
                    "Architecture, integrations, scalability, technical fit",
                    30,
                    10,
                    1,
                ),
                (
                    2,
                    "Implementation Plan",
                    "Timeline, milestones, staffing, risk plan",
                    20,
                    10,
                    1,
                ),
                (
                    3,
                    "Commercial Value",
                    "Pricing clarity, total cost, assumptions",
                    20,
                    10,
                    1,
                ),
                (
                    4,
                    "Security & Compliance",
                    "Controls, certifications, privacy, auditability",
                    20,
                    10,
                    1,
                ),
                (
                    5,
                    "Support & Experience",
                    "Support model, similar projects, references",
                    10,
                    10,
                    1,
                ),
            ]

            conn.executemany(
                """
                INSERT INTO evaluation_criteria
                (criterion_id, name, description, weight, max_score, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                default_criteria,
            )
            conn.commit()

    def get_active_criteria(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT criterion_id, name, description, weight, max_score, is_active
                FROM evaluation_criteria
                WHERE is_active = 1
                ORDER BY criterion_id
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def save_proposal_chunks(
        self,
        document_hash: str,
        source_name: str,
        supplier_name: str,
        chunks: list[dict[str, Any]],
        embedding_model: str | None = None,
    ) -> None:
        vector_rows = []
        vector_dimension = None
        for chunk in chunks:
            embedding = chunk.get("embedding")
            if embedding is None:
                continue
            if not isinstance(embedding, list) or not embedding:
                raise ValueError("Each stored embedding must be a non-empty list of numbers.")
            if any(not isinstance(value, (int, float)) for value in embedding):
                raise ValueError("Embedding vectors must contain only numbers.")
            if vector_dimension is None:
                vector_dimension = len(embedding)
            elif len(embedding) != vector_dimension:
                raise ValueError("All embeddings in one document must have the same dimension.")
            vector_rows.append((int(chunk["chunk_index"]), embedding))

        if vector_rows and len(vector_rows) != len(chunks):
            raise ValueError("Cannot index proposal chunks without embeddings for every chunk.")

        with self._connect() as conn:
            vec_module = None
            vector_table = None
            if vector_rows:
                vec_module = self._load_sqlite_vec(conn)
                vector_table = self._ensure_vector_table(conn, vector_dimension)
            conn.execute("DELETE FROM proposal_chunks WHERE document_hash = ?", (document_hash,))
            conn.executemany(
                """
                INSERT INTO proposal_chunks (
                    document_hash, source_name, supplier_name, chunk_index,
                    chunk_text, word_count, page_start, page_end, heading,
                    section_path_json, boundary_type, embedding_text, embedding_json, embedding_model
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        document_hash,
                        source_name,
                        supplier_name,
                        int(chunk["chunk_index"]),
                        str(chunk["text"]),
                        int(chunk["word_count"]),
                        chunk.get("page_start"),
                        chunk.get("page_end"),
                        chunk.get("heading"),
                        json.dumps(chunk.get("section_path", []), ensure_ascii=False),
                        chunk.get("boundary_type"),
                        str(chunk.get("embedding_text", chunk["text"])),
                        json.dumps(chunk["embedding"]) if chunk.get("embedding") else None,
                        embedding_model if chunk.get("embedding") else None,
                    )
                    for chunk in chunks
                ],
            )

            if vector_table and vec_module:
                conn.execute(
                    f'DELETE FROM "{vector_table}" WHERE document_hash = ? AND embedding_model = ?',
                    (document_hash, embedding_model or ""),
                ).fetchone()
                for chunk_index, embedding in vector_rows:
                    chunk_row = conn.execute(
                        "SELECT rowid FROM proposal_chunks WHERE document_hash = ? AND chunk_index = ?",
                        (document_hash, chunk_index),
                    ).fetchone()
                    conn.execute(
                        f'INSERT INTO "{vector_table}" (rowid, embedding, document_hash, embedding_model) VALUES (?, ?, ?, ?)',
                        (
                            int(chunk_row["rowid"]),
                            vec_module.serialize_float32(embedding),
                            document_hash,
                            embedding_model or "",
                        ),
                    ),
            conn.commit()

    @staticmethod
    def _load_sqlite_vec(conn: sqlite3.Connection) -> Any:
        try:
            import sqlite_vec
        except ImportError as error:
            raise RuntimeError("sqlite-vec is required for vector indexing. Install project requirements.") from error

        conn.enable_load_extension(True)
        try:
            sqlite_vec.load(conn)
        finally:
            conn.enable_load_extension(False)
        return sqlite_vec

    @staticmethod
    def _ensure_vector_table(conn: sqlite3.Connection, dimensions: int) -> str:
        if dimensions < 1:
            raise ValueError("Embedding vectors must have at least one dimension.")
        table_name = f"proposal_vectors_{dimensions}"
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        if not exists:
            conn.execute(
                f"CREATE VIRTUAL TABLE \"{table_name}\" USING vec0("
                f"embedding float[{dimensions}] distance_metric=cosine, "
                "document_hash text partition key, "
                "embedding_model text partition key)"
            )
        return table_name

    def search_similar_chunks(
        self,
        document_hash: str,
        embedding_model: str,
        query_embedding: list[float],
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        table_name = f"proposal_vectors_{len(query_embedding)}"
        with closing(self._connect_readonly()) as conn:
            vec_module = self._load_sqlite_vec(conn)
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
            if not exists:
                return []
            rows = conn.execute(
                f"""
                  SELECT chunks.chunk_index, chunks.chunk_text, chunks.word_count,
                      chunks.source_name, chunks.page_start, chunks.page_end,
                      chunks.heading, chunks.section_path_json, knn.distance
                FROM "{table_name}" AS knn
                JOIN proposal_chunks AS chunks ON chunks.rowid = knn.rowid
                WHERE knn.embedding MATCH ?
                  AND knn.k = ?
                  AND knn.document_hash = ?
                  AND knn.embedding_model = ?
                ORDER BY knn.distance
                """,
                (
                    vec_module.serialize_float32(query_embedding),
                    top_k,
                    document_hash,
                    embedding_model or "",
                ),
            ).fetchall()
            return [
                {
                    "chunk_index": int(row["chunk_index"]),
                    "text": str(row["chunk_text"]),
                    "word_count": int(row["word_count"]),
                    "source_name": str(row["source_name"]),
                    "page_start": row["page_start"],
                    "page_end": row["page_end"],
                    "heading": row["heading"] or "",
                    "section_path": json.loads(row["section_path_json"] or "[]"),
                    "retrieval_score": 1.0 - (float(row["distance"]) / 2.0),
                    "distance": float(row["distance"]),
                    "retrieval_method": "sqlite-vec",
                }
                for row in rows
            ]

    def get_chunk_documents(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT document_hash, source_name, supplier_name,
                       COUNT(*) AS chunk_count,
                       MAX(created_at) AS created_at,
                       MAX(embedding_model) AS embedding_model
                FROM proposal_chunks
                GROUP BY document_hash, source_name, supplier_name
                ORDER BY created_at DESC, source_name COLLATE NOCASE
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def get_proposal_chunks(self, document_hash: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                  SELECT chunk_index, chunk_text, word_count, page_start, page_end, heading,
                      section_path_json, boundary_type, embedding_text, source_name,
                      embedding_json, embedding_model
                FROM proposal_chunks
                WHERE document_hash = ?
                ORDER BY chunk_index
                """,
                (document_hash,),
            ).fetchall()
            chunks = []
            for row in rows:
                item = dict(row)
                item["text"] = item.pop("chunk_text")
                item["section_path"] = json.loads(item.pop("section_path_json") or "[]")
                item["embedding_text"] = item.get("embedding_text") or item["text"]
                item["embedding"] = json.loads(item.pop("embedding_json")) if item.get("embedding_json") else None
                chunks.append(item)
            return chunks

    def create_run(self, status: str = "pending") -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO rfp_runs (status) VALUES (?)",
                (status,),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def save_supplier_result(
        self,
        rfp_run_id: int,
        supplier_name: str,
        submission_date: str,
        experience_rating: float,
        absolute_score: float,
        ppi: float,
        final_rank: int,
        result_json: dict[str, Any],
        warnings: list[str] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO supplier_results (
                    rfp_run_id,
                    supplier_name,
                    submission_date,
                    experience_rating,
                    absolute_score,
                    ppi,
                    final_rank,
                    result_json,
                    warnings
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rfp_run_id,
                    supplier_name,
                    submission_date,
                    experience_rating,
                    absolute_score,
                    ppi,
                    final_rank,
                    json.dumps(result_json, ensure_ascii=False),
                    json.dumps(warnings or [], ensure_ascii=False),
                ),
            )
            conn.commit()

    def get_all_runs(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT rfp_run_id, created_at, status FROM rfp_runs ORDER BY rfp_run_id DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_supplier_results(self, rfp_run_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT supplier_name, submission_date, experience_rating, absolute_score,
                       ppi, final_rank, result_json, warnings
                FROM supplier_results
                WHERE rfp_run_id = ?
                ORDER BY final_rank, supplier_name COLLATE NOCASE
                """,
                (rfp_run_id,),
            ).fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["result"] = json.loads(item.pop("result_json"))
                item["warnings"] = json.loads(item["warnings"] or "[]")
                results.append(item)
            return results
