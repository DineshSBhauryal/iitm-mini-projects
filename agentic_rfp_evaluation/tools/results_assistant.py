from __future__ import annotations

import json
import re
from typing import Any, Callable


def supplier_anchor(supplier_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", supplier_name.lower()).strip("-")
    return f"supplier-{slug or 'unknown'}"


def criterion_anchor(supplier_name: str, criterion_name: str) -> str:
    return f"{supplier_anchor(supplier_name)}-{supplier_anchor(criterion_name).removeprefix('supplier-')}"


def _normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _as_text(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value or "")


def _build_grounding_context(
    results: list[dict[str, Any]],
    source_link: Callable[[str, int | None], str] | None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    context = []
    citation_anchors = {}
    for supplier_index, result in enumerate(results, start=1):
        supplier_name = str(result.get("supplier_name", "Supplier"))
        supplier_reference = f"S{supplier_index}"
        citation_anchors[supplier_reference] = supplier_anchor(supplier_name)
        supplier_context = {
            "reference": supplier_reference,
            "supplier": supplier_name,
            "rank": result.get("final_rank"),
            "absolute_score": result.get("absolute_score"),
            "ppi": result.get("ppi"),
            "overall_summary": result.get("overall_summary", ""),
            "risks": result.get("risks", []),
            "criteria": [],
        }
        for criterion_index, criterion in enumerate(result.get("criteria", []), start=1):
            criterion_reference = f"S{supplier_index}C{criterion_index}"
            criterion_name = str(criterion.get("name", f"Criterion {criterion_index}"))
            citation_anchors[criterion_reference] = criterion_anchor(supplier_name, criterion_name)
            rag_context = criterion.get("rag_context", {})
            retrieved_evidence = [
                {
                    "reference": f"{criterion_reference}E{evidence_index}",
                    "chunk_index": chunk.get("chunk_index"),
                    "source_name": chunk.get("source_name", ""),
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "section_path": chunk.get("section_path", []),
                    "text": str(chunk.get("text", ""))[:700],
                }
                for evidence_index, chunk in enumerate(rag_context.get("retrieved_chunks", [])[:3], start=1)
            ] if isinstance(rag_context, dict) else []
            for evidence in retrieved_evidence:
                citation_anchors[evidence["reference"]] = (
                    source_link(str(evidence["source_name"]), evidence["page_start"])
                    if source_link and evidence.get("source_name") and evidence.get("page_start")
                    else criterion_anchor(supplier_name, criterion_name)
                )
            supplier_context["criteria"].append({
                "reference": criterion_reference,
                "name": criterion_name,
                "score": criterion.get("score"),
                "max_score": criterion.get("max_score"),
                "justification": str(criterion.get("justification", ""))[:700],
                "evidence": str(criterion.get("evidence", ""))[:700],
                "retrieved_evidence": retrieved_evidence,
            })
        context.append(supplier_context)
    return context, citation_anchors


def answer_results_question(
    question: str,
    results: list[dict[str, Any]],
    llm_chat: Callable[[list[dict[str, str]]], str] | None = None,
    source_link: Callable[[str, int | None], str] | None = None,
) -> str:
    """Answer from saved scorecards, using the LLM when provided, with source links."""
    if not results:
        return "There are no saved evaluation results to discuss yet. Run an evaluation first."

    query = _normalized(question)
    if not query:
        return "Ask about a supplier, ranking, criterion score, evidence, or risk."

    if llm_chat is not None:
        context, citation_anchors = _build_grounding_context(results, source_link)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an RFP evaluation results assistant. Answer only from the supplied saved evaluation data. "
                    "Do not invent facts, scores, or evidence. Explain uncertainty when the data does not answer the question. "
                    "Cite every factual claim using exact reference tokens in square brackets. "
                    "Use criterion references like [S1C2] for scorecard claims and evidence references like [S1C2E1] "
                    "for proposal excerpts and page locations. "
                    "Use concise Markdown and do not create URLs."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\nSaved evaluation data (JSON):\n"
                    f"{json.dumps(context, ensure_ascii=False)}"
                ),
            },
        ]
        answer = llm_chat(messages).strip()
        if not answer:
            raise ValueError("The LLM returned an empty answer.")
        citation_pattern = r"\[(S\d+(?:C\d+)?(?:E\d+)?)\]"
        cited_references = set(re.findall(citation_pattern, answer))
        answer = re.sub(citation_pattern, lambda match: match.group(1), answer)
        links = [
            f"[{reference}]({citation_anchors[reference] if citation_anchors[reference].startswith(('file:', 'http:', 'https:')) else f'#{citation_anchors[reference]}'})"
            for reference in sorted(cited_references)
            if reference in citation_anchors
        ]
        answer = re.sub(citation_pattern, "", answer)
        if links:
            answer = f"{answer}\n\nSources: " + " · ".join(links)
        return answer

    suppliers = [
        result for result in results
        if _normalized(str(result.get("supplier_name", ""))) in query
    ]
    criteria = []
    for result in results:
        for criterion in result.get("criteria", []):
            criterion_name = str(criterion.get("name", ""))
            if criterion_name and _normalized(criterion_name) in query:
                criteria.append(criterion_name)
    criterion_names = set(criteria)

    ranking_question = any(
        phrase in query
        for phrase in ("rank", "ranking", "compare", "best", "winner", "who won", "top supplier")
    )
    if ranking_question and not criterion_names:
        ordered = sorted(results, key=lambda result: int(result.get("final_rank", 9999)))
        lines = ["Saved supplier ranking:"]
        for result in ordered:
            name = str(result.get("supplier_name", "Supplier"))
            rank = result.get("final_rank", "?")
            score = result.get("absolute_score", 0)
            ppi = result.get("ppi", 0)
            lines.append(
                f"- **#{rank} {name}**: absolute score {score}, PPI {ppi}. "
                f"[Open scorecard](#{supplier_anchor(name)})."
            )
        return "\n".join(lines)

    target_results = suppliers or results
    if criterion_names:
        lines = []
        for result in target_results:
            name = str(result.get("supplier_name", "Supplier"))
            matching = [
                item for item in result.get("criteria", [])
                if str(item.get("name", "")) in criterion_names
            ]
            for criterion in matching:
                criterion_name = str(criterion.get("name", "Criterion"))
                score = criterion.get("score", "N/A")
                max_score = criterion.get("max_score", 10)
                justification = _as_text(criterion.get("justification"))
                evidence = _as_text(criterion.get("evidence"))
                lines.append(
                    f"- **{name} · {criterion_name}: {score}/{max_score}.** "
                    f"{justification} Evidence: {evidence or 'No evidence text was saved.'} "
                    f"[Open scorecard](#{supplier_anchor(name)})."
                )
        if lines:
            return "\n".join(lines)

    lines = []
    for result in target_results:
        name = str(result.get("supplier_name", "Supplier"))
        summary = _as_text(result.get("overall_summary")) or "No overall summary was saved."
        score = result.get("absolute_score", 0)
        ppi = result.get("ppi", 0)
        lines.append(
            f"**{name}** is ranked #{result.get('final_rank', '?')} with an absolute score "
            f"of {score} and PPI {ppi}. {summary} [Open scorecard](#{supplier_anchor(name)})."
        )
        risks = result.get("risks", [])
        if risks:
            lines.append("Saved risks: " + "; ".join(str(risk) for risk in risks))

    if not suppliers:
        lines.insert(0, "I could not identify a supplier or criterion in that question, so here is the saved run summary:")
    return "\n\n".join(lines)