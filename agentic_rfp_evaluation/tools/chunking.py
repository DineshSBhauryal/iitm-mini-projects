from __future__ import annotations

import math
import re
from typing import Any, Callable


def _is_heading(paragraph: str) -> bool:
    words = paragraph.split()
    if not words or len(words) > 14:
        return False
    return (
        paragraph.isupper()
        or bool(re.match(r"^(?:section\s+)?\d+(?:\.\d+)*[.)]?\s+", paragraph, re.IGNORECASE))
        or (not re.search(r"[.!?;:]$", paragraph) and len(words) <= 9)
    )


def _paragraph_units(
    paragraph: str,
    chunk_size_words: int,
    page_number: int | None = None,
) -> list[tuple[str, str, int | None]]:
    if len(paragraph.split()) <= chunk_size_words:
        return [(paragraph, "paragraph", page_number)]

    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", paragraph)
    if len(sentences) == 1:
        words = paragraph.split()
        return [
            (" ".join(words[start : start + chunk_size_words]), "long-sentence fallback", page_number)
            for start in range(0, len(words), chunk_size_words)
        ]

    units: list[tuple[str, str, int | None]] = []
    current: list[str] = []
    current_count = 0
    for sentence in sentences:
        sentence_words = sentence.split()
        if len(sentence_words) > chunk_size_words:
            if current:
                units.append((" ".join(current), "sentence group", page_number))
                current = []
                current_count = 0
            units.extend(
                (" ".join(sentence_words[start : start + chunk_size_words]), "long-sentence fallback", page_number)
                for start in range(0, len(sentence_words), chunk_size_words)
            )
        elif current and current_count + len(sentence_words) > chunk_size_words:
            units.append((" ".join(current), "sentence group", page_number))
            current = sentence_words
            current_count = len(sentence_words)
        else:
            current.extend(sentence_words)
            current_count += len(sentence_words)
    if current:
        units.append((" ".join(current), "sentence group", page_number))
    return units


def _add_heading_to_path(section_path: list[str], heading: str) -> list[str]:
    numbered_heading = re.match(r"^(?:section\s+)?(\d+(?:\.\d+)*)[.)]?\s+", heading, re.IGNORECASE)
    if numbered_heading:
        level = numbered_heading.group(1).count(".")
        return [*section_path[:level], heading]
    return [heading]


def split_into_chunks(
    text: str | list[dict[str, Any]],
    chunk_size_words: int = 500,
    overlap_words: int = 80,
) -> list[dict[str, Any]]:
    """Split proposal text along heading, paragraph, and sentence boundaries."""
    if chunk_size_words < 1:
        raise ValueError("chunk_size_words must be at least 1")
    if overlap_words < 0 or overlap_words >= chunk_size_words:
        raise ValueError("overlap_words must be non-negative and smaller than chunk_size_words")

    pages = text if isinstance(text, list) else [{"page_number": None, "text": text}]
    page_paragraphs = [
        (
            page.get("page_number"),
            [re.sub(r"\s+", " ", item).strip() for item in re.split(r"\n\s*\n", str(page.get("text", ""))) if item.strip()],
        )
        for page in pages
    ]
    if not any(paragraphs for _, paragraphs in page_paragraphs):
        return []

    sections: list[tuple[str, list[str], list[tuple[str, str, int | None]]]] = []
    current_heading = ""
    section_path: list[str] = []
    current_units: list[tuple[str, str, int | None]] = []
    for page_number, paragraphs in page_paragraphs:
        for paragraph in paragraphs:
            if _is_heading(paragraph):
                if current_units:
                    sections.append((current_heading, section_path, current_units))
                    current_units = []
                current_heading = paragraph
                section_path = _add_heading_to_path(section_path, paragraph)
                continue
            current_units.extend(_paragraph_units(paragraph, chunk_size_words, page_number))
    if current_units:
        sections.append((current_heading, section_path, current_units))
    if not sections:
        all_paragraphs = [
            (paragraph, "paragraph", page_number)
            for page_number, paragraphs in page_paragraphs
            for paragraph in paragraphs
        ]
        sections = [("", [], all_paragraphs)]

    chunks: list[dict[str, Any]] = []
    for heading, current_section_path, units in sections:
        start = 0
        while start < len(units):
            end = start
            word_count = 0
            while end < len(units):
                unit_word_count = len(units[end][0].split())
                if end > start and word_count + unit_word_count > chunk_size_words:
                    break
                word_count += unit_word_count
                end += 1

            selected_units = units[start:end]
            body = "\n\n".join(unit for unit, _, _ in selected_units)
            chunk_text = f"{heading}\n\n{body}" if heading else body
            page_numbers = [page_number for _, _, page_number in selected_units if page_number is not None]
            section_label = " > ".join(current_section_path)
            embedding_text = f"Section: {section_label}\n\n{chunk_text}" if section_label else chunk_text
            chunks.append({
                "chunk_index": len(chunks),
                "text": chunk_text,
                "embedding_text": embedding_text,
                "word_count": len(chunk_text.split()),
                "heading": heading,
                "section_path": list(current_section_path),
                "page_start": min(page_numbers) if page_numbers else None,
                "page_end": max(page_numbers) if page_numbers else None,
                "boundary_type": ", ".join(sorted({kind for _, kind, _ in selected_units})),
            })
            if end >= len(units):
                break

            next_start = end
            overlap_count = 0
            while next_start > start + 1:
                candidate_count = len(units[next_start - 1][0].split())
                if overlap_count + candidate_count > overlap_words:
                    break
                overlap_count += candidate_count
                next_start -= 1
            start = next_start

    return chunks


def rank_chunks_by_keywords(
    chunks: list[dict[str, Any]],
    keywords: list[str],
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Return chunks ranked by how many criterion keywords they contain."""
    ranked = []
    for chunk in chunks:
        text = str(chunk.get("text", ""))
        lowered = text.lower()
        matched = [keyword for keyword in keywords if keyword.lower() in lowered]
        if matched:
            ranked.append({
                **chunk,
                "matched_keywords": matched,
                "retrieval_score": len(matched) / max(len(keywords), 1),
            })
    return sorted(ranked, key=lambda item: item["retrieval_score"], reverse=True)[:top_k]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot_product = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def rank_chunks_by_embedding(
    chunks: list[dict[str, Any]],
    query_embedding: list[float],
    top_k: int = 3,
) -> list[dict[str, Any]]:
    ranked = []
    for chunk in chunks:
        embedding = chunk.get("embedding")
        if not isinstance(embedding, list):
            continue
        ranked.append({
            **chunk,
            "retrieval_score": cosine_similarity(query_embedding, embedding),
        })
    return sorted(ranked, key=lambda item: item["retrieval_score"], reverse=True)[:top_k]


def ensure_chunk_embeddings(
    chunks: list[dict[str, Any]],
    cached_chunks: list[dict[str, Any]],
    embedding_model: str,
    embed_texts: Callable[[list[str], str], list[list[float]]],
) -> tuple[list[dict[str, Any]], bool]:
    """Reuse complete matching embeddings or generate and validate them once."""
    cache_matches = (
        len(chunks) == len(cached_chunks)
        and all(
            current.get("embedding_text", current["text"])
            == cached.get("embedding_text", cached["text"])
            and cached.get("embedding")
            and cached.get("embedding_model") == embedding_model
            for current, cached in zip(chunks, cached_chunks)
        )
    )
    if cache_matches:
        return [
            {**chunk, "embedding": cached["embedding"]}
            for chunk, cached in zip(chunks, cached_chunks)
        ], True

    vectors = embed_texts(
        [str(chunk.get("embedding_text", chunk["text"])) for chunk in chunks],
        embedding_model,
    )
    if len(vectors) != len(chunks) or any(not vector for vector in vectors):
        raise ValueError("The embedding provider returned an incomplete vector set.")

    return [
        {**chunk, "embedding": vector}
        for chunk, vector in zip(chunks, vectors)
    ], False
