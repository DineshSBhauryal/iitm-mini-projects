from pathlib import Path
import sqlite3

from database.db_manager import DatabaseManager
from tools.chunking import (
    ensure_chunk_embeddings,
    rank_chunks_by_embedding,
    rank_chunks_by_keywords,
    split_into_chunks,
)
from tools.evaluation_agent import RAGEvaluationAgent


def test_split_into_chunks_preserves_paragraphs_and_heading_context():
    text = "TECHNICAL APPROACH\n\nThe platform uses modular architecture and API integration."
    chunks = split_into_chunks(text, chunk_size_words=12, overlap_words=3)

    assert len(chunks) == 1
    assert chunks[0]["heading"] == "TECHNICAL APPROACH"
    assert chunks[0]["text"].startswith("TECHNICAL APPROACH")
    assert chunks[0]["boundary_type"] == "paragraph"
    assert chunks[0]["section_path"] == ["TECHNICAL APPROACH"]
    assert chunks[0]["page_start"] is None


def test_split_into_chunks_splits_long_paragraph_at_sentence_boundaries():
    text = (
        "IMPLEMENTATION PLAN\n\n"
        "Discovery defines requirements and delivery risks. "
        "The rollout then proceeds through testing and go-live."
    )
    chunks = split_into_chunks(text, chunk_size_words=8, overlap_words=0)

    assert len(chunks) == 2
    assert all(chunk["heading"] == "IMPLEMENTATION PLAN" for chunk in chunks)
    assert all(chunk["boundary_type"] == "sentence group" for chunk in chunks)
    assert "Discovery defines requirements" in chunks[0]["text"]
    assert "rollout then proceeds" in chunks[1]["text"]


def test_split_into_chunks_uses_hard_cap_for_oversized_sentences():
    chunks = split_into_chunks(" ".join(f"word{i}" for i in range(11)), chunk_size_words=5, overlap_words=0)

    assert [chunk["word_count"] for chunk in chunks] == [5, 5, 1]
    assert chunks[-1]["text"].split()[-1] == "word10"


def test_page_aware_chunks_track_page_ranges_and_hierarchical_sections():
    pages = [
        {"page_number": 1, "text": "1. DELIVERY\n\n1.1 Timeline\n\nMilestones are documented."},
        {"page_number": 2, "text": "Resourcing is phased by workstream."},
    ]

    chunks = split_into_chunks(pages, chunk_size_words=30, overlap_words=0)

    assert len(chunks) == 1
    assert chunks[0]["page_start"] == 1
    assert chunks[0]["page_end"] == 2
    assert chunks[0]["section_path"] == ["1. DELIVERY", "1.1 Timeline"]
    assert chunks[0]["embedding_text"].startswith("Section: 1. DELIVERY > 1.1 Timeline")


def test_embedding_cache_invalidates_when_section_metadata_changes():
    original = [{"chunk_index": 0, "text": "shared text", "embedding_text": "Section A\n\nshared text"}]
    calls = []

    def embed_texts(texts, model):
        calls.append(texts)
        return [[0.2, 0.8]]

    indexed, _ = ensure_chunk_embeddings(original, [], "embed-model", embed_texts)
    updated = [{"chunk_index": 0, "text": "shared text", "embedding_text": "Section B\n\nshared text"}]
    reindexed, reused = ensure_chunk_embeddings(
        updated,
        [dict(indexed[0], embedding_model="embed-model")],
        "embed-model",
        embed_texts,
    )

    assert reused is False
    assert reindexed[0]["embedding"] == [0.2, 0.8]
    assert calls == [[original[0]["embedding_text"]], [updated[0]["embedding_text"]]]


def test_chunk_retrieval_ranks_keywords_and_embeddings():
    chunks = split_into_chunks("architecture integration delivery risk", chunk_size_words=3, overlap_words=1)
    keyword_results = rank_chunks_by_keywords(chunks, ["architecture", "integration"])
    embedded_chunks = [dict(chunk, embedding=[1.0, 0.0]) for chunk in chunks]
    embedding_results = rank_chunks_by_embedding(embedded_chunks, [1.0, 0.0])

    assert keyword_results
    assert keyword_results[0]["retrieval_score"] > 0
    assert embedding_results[0]["retrieval_score"] == 1.0


def test_embeddings_are_generated_once_and_reused_for_same_model():
    chunks = [{"chunk_index": 0, "text": "proposal chunk", "word_count": 2}]
    calls = []

    def embed_texts(texts, model):
        calls.append((texts, model))
        return [[0.1, 0.9]]

    indexed, reused_first_time = ensure_chunk_embeddings(chunks, [], "embed-model", embed_texts)
    cache_rows = [dict(indexed[0], embedding_model="embed-model")]
    reindexed, reused_second_time = ensure_chunk_embeddings(chunks, cache_rows, "embed-model", embed_texts)

    assert reused_first_time is False
    assert reused_second_time is True
    assert indexed[0]["embedding"] == reindexed[0]["embedding"] == [0.1, 0.9]
    assert len(calls) == 1


def test_sqlite_persists_chunk_text_and_embedding(tmp_path: Path):
    manager = DatabaseManager(tmp_path / "chunks.db")
    chunks = [{
        "chunk_index": 0,
        "text": "architecture integration details",
        "word_count": 3,
        "embedding": [0.25, 0.75],
    }]

    manager.save_proposal_chunks("doc-hash", "proposal.pdf", "Supplier", chunks, "test-embedding")
    documents = manager.get_chunk_documents()
    stored_chunks = manager.get_proposal_chunks("doc-hash")

    assert documents[0]["chunk_count"] == 1
    assert documents[0]["embedding_model"] == "test-embedding"
    assert stored_chunks[0]["text"] == chunks[0]["text"]
    assert stored_chunks[0]["embedding"] == chunks[0]["embedding"]


def test_sqlite_persists_text_chunks_without_embeddings(tmp_path: Path):
    manager = DatabaseManager(tmp_path / "text-only-chunks.db")
    chunks = [{"chunk_index": 0, "text": "keyword retrieval proposal text", "word_count": 4}]

    manager.save_proposal_chunks("doc-hash", "proposal.pdf", "Supplier", chunks)
    stored_chunks = manager.get_proposal_chunks("doc-hash")

    assert len(stored_chunks) == 1
    assert stored_chunks[0]["text"] == chunks[0]["text"]
    assert stored_chunks[0]["embedding"] is None


def test_sqlite_persists_chunk_provenance_and_enriched_embedding_text(tmp_path: Path):
    manager = DatabaseManager(tmp_path / "provenance.db")
    chunks = [{
        "chunk_index": 0,
        "text": "The rollout is phased.",
        "embedding_text": "Section: IMPLEMENTATION > Timeline\n\nThe rollout is phased.",
        "word_count": 4,
        "page_start": 2,
        "page_end": 3,
        "heading": "Timeline",
        "section_path": ["IMPLEMENTATION", "Timeline"],
        "boundary_type": "paragraph",
        "embedding": [0.1, 0.9],
    }]

    manager.save_proposal_chunks("doc-hash", "proposal.pdf", "Supplier", chunks, "embed-model")
    stored = manager.get_proposal_chunks("doc-hash")[0]

    assert stored["page_start"] == 2
    assert stored["page_end"] == 3
    assert stored["section_path"] == ["IMPLEMENTATION", "Timeline"]
    assert stored["embedding_text"] == chunks[0]["embedding_text"]
    assert stored["source_name"] == "proposal.pdf"


def test_database_migrates_legacy_chunk_table(tmp_path: Path):
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """CREATE TABLE proposal_chunks (
                document_hash TEXT NOT NULL,
                source_name TEXT NOT NULL,
                supplier_name TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                word_count INTEGER NOT NULL,
                embedding_json TEXT,
                embedding_model TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (document_hash, chunk_index)
            )"""
        )

    manager = DatabaseManager(database_path)
    columns = {column["name"] for column in next(table for table in manager.list_tables() if table["name"] == "proposal_chunks")["columns"]}

    assert {"page_start", "page_end", "heading", "section_path_json", "boundary_type", "embedding_text"} <= columns


def test_sqlite_vec_search_returns_nearest_chunk_scoped_to_document_and_model(tmp_path: Path):
    manager = DatabaseManager(tmp_path / "vectors.db")
    manager.save_proposal_chunks(
        "doc-a",
        "proposal-a.pdf",
        "Supplier A",
        [
            {"chunk_index": 0, "text": "technical architecture", "word_count": 2, "embedding": [1.0, 0.0]},
            {"chunk_index": 1, "text": "commercial pricing", "word_count": 2, "embedding": [0.0, 1.0]},
        ],
        "model-a",
    )
    manager.save_proposal_chunks(
        "doc-b",
        "proposal-b.pdf",
        "Supplier B",
        [{"chunk_index": 0, "text": "other supplier text", "word_count": 3, "embedding": [0.99, 0.01]}],
        "model-a",
    )

    results = manager.search_similar_chunks("doc-a", "model-a", [0.99, 0.01], top_k=2)

    assert [result["chunk_index"] for result in results] == [0, 1]
    assert results[0]["text"] == "technical architecture"
    assert results[0]["retrieval_method"] == "sqlite-vec"
    assert results[0]["retrieval_score"] > results[1]["retrieval_score"]
    vector_table = next(table for table in manager.list_tables() if table["name"] == "proposal_vectors_2")
    assert vector_table["row_count"] == 3
    columns, vector_rows, truncated = manager.query_readonly(
        "SELECT rowid, document_hash, embedding_model FROM proposal_vectors_2 ORDER BY rowid"
    )
    assert columns == ["rowid", "document_hash", "embedding_model"]
    assert len(vector_rows) == 3
    assert truncated is False


def test_evaluation_uses_retrieved_chunks_for_evidence():
    criteria = [{"criterion_id": 1, "name": "Technical Capability", "max_score": 10}]
    retrieved_chunks = {
        "Technical Capability": [{
            "chunk_index": 2,
            "text": "API architecture integration details",
            "retrieval_score": 0.8,
            "matched_keywords": ["api", "architecture"],
            "retrieval_method": "keyword",
            "source_name": "nexaworks.pdf",
            "page_start": 2,
            "page_end": 3,
            "section_path": ["TECHNICAL RESPONSE", "Architecture"],
        }]
    }

    result = RAGEvaluationAgent(criteria, use_rag=True).score_supplier(
        "NexaWorks",
        "unrelated proposal text",
        "2026-10-25",
        5,
        retrieved_chunks,
    )

    criterion_result = result["criteria"][0]
    assert criterion_result["rag_context"]["retrieved_chunks"][0]["chunk_index"] == 2
    assert "architecture" in criterion_result["evidence"]
    assert "integration" in criterion_result["evidence"]
    assert result["retrieval_preview"][0]["retrieved_chunks"]
    retrieved_evidence = criterion_result["rag_context"]["retrieved_chunks"][0]
    assert retrieved_evidence["source_name"] == "nexaworks.pdf"
    assert retrieved_evidence["page_start"] == 2
    assert retrieved_evidence["section_path"] == ["TECHNICAL RESPONSE", "Architecture"]
