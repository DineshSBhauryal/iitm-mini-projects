from __future__ import annotations

from pathlib import Path


try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None


class DocumentTool:
    """Extracts text from uploaded PDFs."""

    def extract_text(self, pdf_path: str | Path) -> str:
        return "\n\n".join(
            page["text"] for page in self.extract_pages(pdf_path) if page["text"]
        )

    def extract_pages(self, pdf_path: str | Path) -> list[dict[str, int | str]]:
        """Extract text per PDF page, preserving 1-based page numbers."""
        path = Path(pdf_path)

        if fitz is not None:
            with fitz.open(path) as document:
                pages = []
                for page_number, page in enumerate(document, start=1):
                    text = page.get_text("text")
                    pages.append({"page_number": page_number, "text": text.strip()})
                return pages

        raise ImportError("PyMuPDF is not installed. Install requirements.txt before using PDF parsing.")
