from database.db_manager import DatabaseManager
from tools.results_assistant import answer_results_question, criterion_anchor, supplier_anchor


def test_results_assistant_answers_criterion_question_with_evidence_link():
    results = [{
        "supplier_name": "North Star Systems",
        "final_rank": 1,
        "criteria": [{
            "name": "Security & Compliance",
            "score": 8,
            "max_score": 10,
            "justification": "Strong documented controls.",
            "evidence": "The proposal describes annual penetration testing.",
        }],
    }]

    answer = answer_results_question("How did North Star Systems score on Security & Compliance?", results)

    assert "8/10" in answer
    assert "annual penetration testing" in answer
    assert f"(#{supplier_anchor('North Star Systems')})" in answer


def test_results_assistant_summarizes_ranking_with_links():
    results = [
        {"supplier_name": "Second Supplier", "final_rank": 2, "absolute_score": 72, "ppi": 0.8},
        {"supplier_name": "First Supplier", "final_rank": 1, "absolute_score": 91, "ppi": 1.0},
    ]

    answer = answer_results_question("Who ranked first?", results)

    assert answer.index("First Supplier") < answer.index("Second Supplier")
    assert f"(#{supplier_anchor('First Supplier')})" in answer
    assert f"(#{supplier_anchor('Second Supplier')})" in answer


def test_results_assistant_uses_llm_with_saved_evidence_and_resolves_citations():
    results = [{
        "supplier_name": "North Star Systems",
        "final_rank": 1,
        "criteria": [{
            "name": "Security & Compliance",
            "score": 8,
            "max_score": 10,
            "justification": "Strong documented controls.",
            "evidence": "Annual penetration testing is described.",
            "rag_context": {
                "retrieved_chunks": [{
                    "chunk_index": 1,
                    "source_name": "north_star.pdf",
                    "page_start": 4,
                    "page_end": 5,
                    "section_path": ["Security", "Testing"],
                    "text": "Annual penetration testing is described.",
                }],
            },
        }],
    }]
    calls = []

    def fake_llm(messages):
        calls.append(messages)
        return "North Star scored 8/10 based on annual testing [S1C1]."

    answer = answer_results_question(
        "Why did North Star score well on security?",
        results,
        llm_chat=fake_llm,
    )

    prompt = calls[0][1]["content"]
    assert "Annual penetration testing is described." in prompt
    assert "page_start" in prompt
    assert "section_path" in prompt
    assert "North Star scored 8/10" in answer
    assert f"[S1C1](#{criterion_anchor('North Star Systems', 'Security & Compliance')})" in answer


def test_results_assistant_ignores_unknown_llm_citation_tokens():
    result = answer_results_question(
        "Summarize the supplier",
        [{"supplier_name": "North Star Systems", "criteria": []}],
        llm_chat=lambda messages: "Unsupported claim [S9].",
    )

    assert "[S9]" not in result
    assert "Sources:" not in result


def test_results_assistant_links_evidence_citation_to_pdf_page():
    results = [{
        "supplier_name": "North Star Systems",
        "criteria": [{
            "name": "Security & Compliance",
            "score": 8,
            "max_score": 10,
            "evidence": "Annual penetration testing is described.",
            "rag_context": {
                "retrieved_chunks": [{
                    "chunk_index": 2,
                    "source_name": "north_star.pdf",
                    "page_start": 4,
                    "page_end": 5,
                    "section_path": ["Security", "Testing"],
                    "text": "Annual penetration testing is performed.",
                }],
            },
        }],
    }]

    answer = answer_results_question(
        "What security evidence was provided?",
        results,
        llm_chat=lambda messages: "The proposal describes annual testing [S1C1E1].",
        source_link=lambda source, page: f"file:///uploads/{source}#page={page}",
    )

    assert "[S1C1E1](file:///uploads/north_star.pdf#page=4)" in answer


def test_database_loads_saved_results_for_a_run(tmp_path):
    manager = DatabaseManager(tmp_path / "results.db")
    run_id = manager.create_run(status="completed")
    manager.save_supplier_result(
        rfp_run_id=run_id,
        supplier_name="North Star Systems",
        submission_date="2026-10-25",
        experience_rating=8,
        absolute_score=82.5,
        ppi=0.94,
        final_rank=1,
        result_json={"criteria": [{"name": "Security & Compliance", "score": 8}]},
        warnings=["Review the delivery timeline."],
    )

    rows = manager.get_supplier_results(run_id)

    assert rows[0]["supplier_name"] == "North Star Systems"
    assert rows[0]["result"]["criteria"][0]["score"] == 8
    assert rows[0]["warnings"] == ["Review the delivery timeline."]