from pathlib import Path

import fitz

from scripts.generate_sample_pdfs import generate_sample_pdfs
from tools.document_tool import DocumentTool


def test_sample_proposals_are_structured_extractable_and_supplier_specific(tmp_path: Path):
    generated = generate_sample_pdfs(tmp_path)

    assert len(generated) == 4
    assert {path.name for path in generated} == {
        "apex_systems_proposal.pdf",
        "brightpath_tech_proposal.pdf",
        "nexaworks_proposal.pdf",
        "orbit_digital_proposal.pdf",
    }

    extracted_by_file = {}
    for path in generated:
        with fitz.open(path) as document:
            assert document.page_count == 4
            assert document.metadata["title"]
            text = "\n".join(page.get_text("text") for page in document)
            assert "EXECUTIVE SUMMARY" in text
            assert "TECHNICAL RESPONSE" in text
            assert "COMMERCIAL AND ASSURANCE" in text
            assert "OPERATING MODEL" in text
            assert "synthetic proposal" in text.lower()
            extracted_by_file[path.name] = text

    assert len({text for text in extracted_by_file.values()}) == 4
    assert "premium" in extracted_by_file["apex_systems_proposal.pdf"].lower()
    assert "lowest" in extracted_by_file["brightpath_tech_proposal.pdf"].lower()


def test_document_tool_extracts_text_with_page_numbers(tmp_path: Path):
    generated = generate_sample_pdfs(tmp_path)

    pages = DocumentTool().extract_pages(generated[0])
    combined_text = DocumentTool().extract_text(generated[0])

    assert [page["page_number"] for page in pages] == [1, 2, 3, 4]
    assert all(page["text"] for page in pages)
    assert "EXECUTIVE SUMMARY" in combined_text
