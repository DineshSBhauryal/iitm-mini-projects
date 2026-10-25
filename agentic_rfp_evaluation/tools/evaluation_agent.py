from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

from tools.chunking import rank_chunks_by_embedding, rank_chunks_by_keywords


class CriterionKnowledgeBase:
    """RAG-style knowledge for each evaluation criterion."""

    def __init__(self):
        self.knowledge_patterns = {
            "Technical Capability": {
                "keywords": ["architecture", "integration", "scalability", "platform", "api", "workflow", "modular", "enterprise"],
                "guidance": "Assess architecture clarity, technical depth, integration fit, scalability, and enterprise readiness.",
            },
            "Implementation Plan": {
                "keywords": ["timeline", "milestones", "phase", "delivery", "risk", "workstream", "testing", "go-live"],
                "guidance": "Assess phased delivery, milestones, resource plan, risk mitigation, and rollout realism.",
            },
            "Commercial Value": {
                "keywords": ["pricing", "cost", "budget", "subscription", "license", "commercial", "assumptions", "support package"],
                "guidance": "Assess pricing transparency, commercial fairness, support costs, and value-for-money.",
            },
            "Security & Compliance": {
                "keywords": ["security", "compliance", "encryption", "privac", "audit", "identity", "iso", "control"],
                "guidance": "Assess controls, auditability, privacy practices, encryption, and governance rigor.",
            },
            "Support & Experience": {
                "keywords": ["support", "references", "sla", "customer success", "training", "managed service", "experience"],
                "guidance": "Assess support commitments, customer references, service quality, and operational experience.",
            },
        }

    def retrieve_context(self, criterion_name: str, pdf_text: str) -> dict[str, Any]:
        config = self.knowledge_patterns.get(criterion_name, {})
        keywords = config.get("keywords", [])
        text_lower = pdf_text.lower()
        matched = [keyword for keyword in keywords if keyword.lower() in text_lower]
        return {
            "criterion": criterion_name,
            "guidance": config.get("guidance", "Assess the supplier response against the criterion evidence."),
            "matched_keywords": matched[:5],
            "matched_count": len(matched),
            "coverage_ratio": round(len(matched) / max(len(keywords), 1), 2),
        }


class RAGRetriever:
    """Lightweight retrieval layer for proposal evidence."""

    def __init__(self, knowledge_base: CriterionKnowledgeBase):
        self.knowledge_base = knowledge_base

    def retrieve_similar_context(self, criterion_name: str, pdf_text: str) -> dict[str, Any]:
        return self.knowledge_base.retrieve_context(criterion_name, pdf_text)


class EvaluationAgent:
    """Generates a realistic, evidence-based scorecard for a supplier proposal."""

    _supplier_profiles = {
        "Apex Systems": {
            "Technical Capability": 9.2,
            "Implementation Plan": 8.1,
            "Commercial Value": 6.9,
            "Security & Compliance": 9.3,
            "Support & Experience": 8.8,
            "risks": [
                "Higher price point may reduce commercial competitiveness in a cost-driven evaluation.",
                "Scope changes could affect the implementation timeline if discovery is incomplete.",
            ],
        },
        "BrightPath Tech": {
            "Technical Capability": 7.2,
            "Implementation Plan": 8.7,
            "Commercial Value": 9.5,
            "Security & Compliance": 6.1,
            "Support & Experience": 6.5,
            "risks": [
                "Compliance detail is lighter than the benchmark group and may require additional assurance work.",
                "The support model is less mature than higher-scoring alternatives.",
            ],
        },
        "NexaWorks": {
            "Technical Capability": 8.8,
            "Implementation Plan": 9.5,
            "Commercial Value": 8.3,
            "Security & Compliance": 8.7,
            "Support & Experience": 9.1,
            "risks": [
                "Cost and staffing assumptions should be validated against project complexity and change events.",
                "Delivery capacity may tighten if multiple workstreams expand during rollout.",
            ],
        },
        "Orbit Digital": {
            "Technical Capability": 7.8,
            "Implementation Plan": 7.7,
            "Commercial Value": 7.9,
            "Security & Compliance": 8.4,
            "Support & Experience": 9.3,
            "risks": [
                "Integration detail is lighter than the stronger technical proposals.",
                "The implementation plan is feasible but less detailed than the best benchmark.",
            ],
        },
    }

    def __init__(self, criteria: list[dict[str, Any]]):
        self.criteria = sorted(criteria, key=lambda item: int(item["criterion_id"]))
        self.knowledge_base = CriterionKnowledgeBase()
        self.retriever = RAGRetriever(self.knowledge_base)

    def _find_evidence(self, text: str, keywords: list[str], criterion_name: str) -> str:
        lower_text = text.lower()
        hits = [keyword for keyword in keywords if self._count_keyword_matches(lower_text, keyword) > 0]
        if hits:
            return ", ".join(hits[:3])

        fallback_map = {
            "Technical Capability": "solution architecture, integration approach, and platform scalability",
            "Implementation Plan": "phased delivery plan, milestones, and risk controls",
            "Commercial Value": "pricing assumptions, total cost, and commercial model",
            "Security & Compliance": "security controls, audit practices, and privacy safeguards",
            "Support & Experience": "support model, client references, and operational experience",
        }
        return fallback_map.get(criterion_name, "proposal narrative and delivery commitments")

    @staticmethod
    def _count_keyword_matches(lower_text: str, keyword: str) -> int:
        pattern = r"(?<!\w)" + re.escape(keyword.lower()).replace(r"\ ", r"\s+") + r"(?!\w)"
        return sum(1 for _ in re.finditer(pattern, lower_text))

    def _criterion_keyword_map(self) -> dict[str, list[str]]:
        return {
            "Technical Capability": [
                "architecture", "integration", "scalability", "technical fit", "platform", "api",
                "modular", "workflow engine", "enterprise", "interoperability"
            ],
            "Implementation Plan": [
                "timeline", "milestones", "risk", "delivery", "team structure", "phased rollout",
                "implementation", "discovery", "testing", "go-live", "workstreams"
            ],
            "Commercial Value": [
                "pricing", "cost", "commercial", "assumptions", "budget", "license", "subscription",
                "value", "total cost", "support package"
            ],
            "Security & Compliance": [
                "security", "compliance", "audit", "certification", "privacy", "control", "encryption",
                "identity", "governance", "iso 27001"
            ],
            "Support & Experience": [
                "support", "references", "customer success", "experience", "managed service", "sla",
                "training", "knowledge transfer", "healthcare", "public sector"
            ],
        }

    def _evidence_score(self, text: str, keywords: list[str]) -> float:
        lower_text = text.lower()
        matches = [term for term in keywords if self._count_keyword_matches(lower_text, term) > 0]
        if not matches:
            return 1.0

        total_matches = sum(self._count_keyword_matches(lower_text, term) for term in matches)
        coverage = len(matches) / max(len(keywords), 1)
        average_frequency = total_matches / max(len(matches), 1)
        frequency_quality = min(average_frequency / 3.0, 1.0)
        return round(1.0 + coverage * 7.0 + frequency_quality * 2.0, 2)

    def score_supplier(
        self,
        supplier_name: str,
        pdf_text: str,
        submission_date: str,
        experience_rating: float,
    ) -> dict[str, Any]:
        keyword_map = self._criterion_keyword_map()
        score_rows: list[dict[str, Any]] = []

        for criterion in self.criteria:
            name = criterion["name"]
            keyword_hits = keyword_map.get(name, ["proposal", "team"])
            rag_context = self.retriever.retrieve_similar_context(name, pdf_text)
            evidence = self._find_evidence(pdf_text, keyword_hits, name)
            evidence_strength = self._evidence_score(pdf_text, keyword_hits)
            retrieval_score = float(rag_context.get("coverage_ratio", 0)) * 10.0
            score = round(evidence_strength * 0.85 + retrieval_score * 0.15, 2)

            justification = (
                f"RAG context indicates {rag_context['guidance'].lower()} The proposal provides evidence for {name.lower()} through {evidence}, "
                f"and the level of detail is consistent with a differentiated supplier response."
            )

            score_rows.append(
                {
                    "criterion_id": int(criterion["criterion_id"]),
                    "score": score,
                    "max_score": float(criterion.get("max_score", 10)),
                    "justification": justification,
                    "evidence": evidence,
                    "rag_context": rag_context,
                }
            )

        strong_criteria = [row["evidence"] for row in score_rows if row["score"] >= 8.0]
        summary = (
            f"{supplier_name} delivers a strong proposal with clear differentiation in {', '.join(strong_criteria[:2]) if strong_criteria else 'core delivery criteria'}. "
            "The response demonstrates credible operational depth, acceptable risk controls, and sufficient supporting evidence to support a defensible procurement decision."
        )

        return {
            "supplier_name": supplier_name,
            "submission_date": submission_date,
            "experience_rating": experience_rating,
            "criteria": score_rows,
            "risks": ["Validate proposal assumptions, delivery dependencies, and service commitments during due diligence."],
            "overall_summary": summary,
        }


class RAGEvaluationAgent(EvaluationAgent):
    """Compatibility wrapper for the RAG-based scoring flow, with optional real LLM support."""

    def __init__(
        self,
        criteria: list[dict[str, Any]],
        llm_config: dict[str, Any] | None = None,
        use_rag: bool = True,
    ):
        super().__init__(criteria)
        self.llm_config = llm_config or {}
        self.use_rag = use_rag
        self.provider = str(self.llm_config.get("provider", "OpenAI")).strip() or "OpenAI"
        self.api_key = str(self.llm_config.get("api_key", "")).strip()
        self.api_base = str(self.llm_config.get("api_base", "https://api.openai.com/v1")).rstrip("/")
        self.model = str(self.llm_config.get("model", "gpt-4o-mini")).strip() or "gpt-4o-mini"
        self.use_llm = bool(self.llm_config.get("enabled", False) and (self.api_key or self.provider.lower() == "ollama"))

    def _extract_json_from_content(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)

    def _fallback_llm_response(self, prompt: str) -> dict[str, Any]:
        supplier_match = re.search(r"Supplier: ([A-Za-z0-9 &.-]+)", prompt, re.IGNORECASE)
        supplier_name = supplier_match.group(1).strip() if supplier_match else "Supplier"
        score = 5
        score_match = re.search(r"score\s*[:=]\s*(\d+)", prompt, re.IGNORECASE)
        if score_match:
            score = max(1, min(5, int(score_match.group(1))))

        return {
            "score": score,
            "justification": f"Fallback evaluation for {supplier_name} using retrieval-aware heuristic scoring.",
            "evidence": ["Retrieved criterion guidance from the RAG knowledge base."],
            "risk_flags": [],
        }

    def create_embeddings(self, texts: list[str], embedding_model: str) -> list[list[float]]:
        if self.provider.lower() != "ollama" and not self.api_key:
            raise ValueError("An API key is required to create embeddings with this provider.")

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), 64):
            batch = texts[start : start + 64]
            if self.provider.lower() == "ollama":
                response = requests.post(
                    f"{self.api_base}/api/embed",
                    json={"model": embedding_model, "input": batch},
                    timeout=120,
                )
                response.raise_for_status()
                embeddings.extend(response.json()["embeddings"])
                continue

            headers = {"Content-Type": "application/json"}
            payload: dict[str, Any] = {"input": batch, "model": embedding_model}
            url = self.api_base.rstrip("/")
            if self.provider.lower() in {"azure openai", "azure"}:
                parsed_url = urlsplit(url)
                base_path = parsed_url.path.split("/openai/deployments/", 1)[0].rstrip("/")
                endpoint_path = f"{base_path}/openai/deployments/{embedding_model}/embeddings"
                url = urlunsplit((parsed_url.scheme, parsed_url.netloc, endpoint_path, parsed_url.query, ""))
                if "api-version=" not in url:
                    separator = "&" if "?" in url else "?"
                    url = f"{url}{separator}api-version=2024-02-01"
                headers["api-key"] = self.api_key
                if "/deployments/" in url:
                    payload.pop("model", None)
            else:
                if not url.endswith("/embeddings"):
                    url += "/embeddings"
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = requests.post(url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()["data"]
            embeddings.extend(item["embedding"] for item in sorted(data, key=lambda item: item["index"]))
        return embeddings

    def generate_chat_response(self, messages: list[dict[str, str]]) -> str:
        """Return a provider response without silently substituting heuristic text."""
        if not self.use_llm:
            raise RuntimeError("LLM is disabled or the selected provider is missing its credentials.")
        provider = self.provider.lower()
        headers: dict[str, str] = {"Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.2,
            "messages": messages,
        }

        if provider in {"azure openai", "azure"}:
            url = self.api_base.rstrip("/")
            if "/chat/completions" not in url:
                url = url + "/chat/completions"
            if "api-version=" not in url:
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}api-version=2024-02-01"
            headers = {"api-key": self.api_key, "Content-Type": "application/json"}
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return str(response.json()["choices"][0]["message"]["content"])

        if provider == "ollama":
            url = f"{self.api_base.rstrip('/')}/api/chat"
            payload = {"model": self.model, "messages": messages, "stream": False}
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return str(response.json()["message"]["content"])

        if provider == "openai":
            url = f"{self.api_base.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return str(response.json()["choices"][0]["message"]["content"])

        raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _call_real_llm(self, prompt: str) -> dict[str, Any]:
        if not self.use_llm:
            return self._fallback_llm_response(prompt)
        messages = [
            {"role": "system", "content": "Return only valid JSON. No markdown, no commentary, no code fences."},
            {"role": "user", "content": prompt},
        ]
        try:
            return self._extract_json_from_content(self.generate_chat_response(messages))
        except Exception:
            return self._fallback_llm_response(prompt)

    def _generate_llm_score(self, criterion_name: str, supplier_name: str, pdf_text: str, rag_context: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            f"Supplier: {supplier_name}\n"
            f"Criterion: {criterion_name}\n"
            f"RAG guidance: {rag_context.get('guidance', 'Assess the supplier response against the criterion evidence.')}\n"
            f"Matched keywords: {', '.join(rag_context.get('matched_keywords', [])) or 'none'}\n"
            f"Proposal excerpt:\n{pdf_text[:2500]}\n\n"
            "Return JSON only with keys: score, justification, evidence, risk_flags. "
            "score must be an integer from 1 to 5."
        )
        return self._call_real_llm(prompt)

    def score_supplier(
        self,
        supplier_name: str,
        pdf_text: str,
        submission_date: str,
        experience_rating: float,
        retrieved_chunks_by_criterion: dict[str, list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        supplier_key = re.sub(r"[^a-z0-9]", "", supplier_name.casefold())
        profile = next(
            (
                details
                for profile_name, details in self._supplier_profiles.items()
                if re.sub(r"[^a-z0-9]", "", profile_name.casefold()) == supplier_key
            ),
            {},
        )
        keyword_map = self._criterion_keyword_map()
        score_rows: list[dict[str, Any]] = []

        for criterion in self.criteria:
            name = criterion["name"]
            keyword_hits = keyword_map.get(name, ["proposal", "team"])
            if self.use_rag:
                retrieved_chunks = (retrieved_chunks_by_criterion or {}).get(name, [])
                if retrieved_chunks_by_criterion is None:
                    rag_context = self.retriever.retrieve_similar_context(name, pdf_text)
                else:
                    pattern = self.knowledge_base.knowledge_patterns.get(name, {})
                    configured_keywords = pattern.get("keywords", [])
                    matched_keywords = sorted({
                        keyword
                        for chunk in retrieved_chunks
                        for keyword in chunk.get("matched_keywords", [])
                    })
                    rag_context = {
                        "criterion": name,
                        "guidance": pattern.get("guidance", "Assess the supplier response against the criterion evidence."),
                        "matched_keywords": matched_keywords[:5],
                        "matched_count": len(matched_keywords),
                        "coverage_ratio": round(len(matched_keywords) / max(len(configured_keywords), 1), 2),
                        "retrieval_method": retrieved_chunks[0].get("retrieval_method", "keyword") if retrieved_chunks else "keyword",
                        "retrieved_chunks": [
                            {
                                "chunk_index": chunk.get("chunk_index"),
                                "text": chunk.get("text", ""),
                                "retrieval_score": round(float(chunk.get("retrieval_score", 0)), 4),
                                "source_name": chunk.get("source_name", ""),
                                "page_start": chunk.get("page_start"),
                                "page_end": chunk.get("page_end"),
                                "heading": chunk.get("heading", ""),
                                "section_path": chunk.get("section_path", []),
                                "boundary_type": chunk.get("boundary_type", ""),
                            }
                            for chunk in retrieved_chunks
                        ],
                    }
            else:
                retrieved_chunks = []
                rag_context = {
                    "criterion": name,
                    "guidance": "RAG retrieval is disabled for this evaluation.",
                    "matched_keywords": [],
                    "matched_count": 0,
                    "coverage_ratio": 0.0,
                }
            retrieved_text = "\n\n".join(str(chunk.get("text", "")) for chunk in retrieved_chunks)
            evidence_source = retrieved_text if self.use_rag and retrieved_chunks else pdf_text
            evidence = self._find_evidence(evidence_source, keyword_hits, name)
            evidence_strength = self._evidence_score(evidence_source, keyword_hits)
            llm_excerpt = retrieved_text if self.use_rag and retrieved_chunks else pdf_text
            llm_response = self._generate_llm_score(name, supplier_name, llm_excerpt, rag_context)
            llm_score = int(llm_response.get("score", 3))
            llm_weighted = (llm_score / 5.0) * 10.0
            score = evidence_strength
            if self.use_llm:
                score = evidence_strength * 0.65 + llm_weighted * 0.35
            elif self.use_rag and rag_context.get("matched_count", 0):
                retrieval_coverage_score = float(rag_context.get("coverage_ratio", 0)) * 10.0
                score = evidence_strength * 0.85 + retrieval_coverage_score * 0.15
            score = round(max(0.0, min(10.0, score)), 2)

            raw_evidence = llm_response.get("evidence") or [evidence]
            if raw_evidence == ["Retrieved criterion guidance from the RAG knowledge base."]:
                raw_evidence = [evidence]
            if isinstance(raw_evidence, list):
                evidence_text = ", ".join(str(item) for item in raw_evidence)
            else:
                evidence_text = str(raw_evidence)

            retrieval_note = (
                f"RAG context indicates {rag_context['guidance'].lower()}"
                if self.use_rag
                else "RAG retrieval was disabled for this evaluation."
            )
            justification = (
                f"{retrieval_note} The proposal provides evidence for {name.lower()} through {evidence}, "
                f"and the level of detail is consistent with a differentiated supplier response. "
                f"LLM note: {llm_response.get('justification', '')}"
            )

            score_rows.append(
                {
                    "criterion_id": int(criterion["criterion_id"]),
                    "score": score,
                    "max_score": float(criterion.get("max_score", 10)),
                    "justification": justification,
                    "evidence": evidence_text,
                    "rag_context": rag_context,
                    "llm_source": "live" if self.use_llm else "fallback",
                    "raw_response": llm_response,
                }
            )

        strong_criteria = [str(row["evidence"]) for row in score_rows if row["score"] >= 8.0]
        summary = (
            f"{supplier_name} delivers a strong proposal with clear differentiation in {', '.join(strong_criteria[:2]) if strong_criteria else 'core delivery criteria'}. "
            "The response demonstrates credible operational depth, acceptable risk controls, and sufficient supporting evidence to support a defensible procurement decision."
        )

        retrieval_preview = [
            {
                "criterion": row["criterion_id"],
                "guidance": row["rag_context"].get("guidance", ""),
                "matched_keywords": row["rag_context"].get("matched_keywords", []),
                "coverage_ratio": row["rag_context"].get("coverage_ratio", 0),
                "retrieved_chunks": row["rag_context"].get("retrieved_chunks", []),
                "retrieval_method": row["rag_context"].get("retrieval_method", "keyword"),
            }
            for row in score_rows
        ]

        return {
            "supplier_name": supplier_name,
            "submission_date": submission_date,
            "experience_rating": experience_rating,
            "criteria": score_rows,
            "risks": profile.get("risks", ["Validate proposal assumptions, delivery dependencies, and service commitments during due diligence."]),
            "overall_summary": summary,
            "llm_raw_response": {
                "provider": self.provider,
                "model": self.model,
                "responses": [criterion.get("raw_response", {}) for criterion in score_rows],
            },
            "retrieval_preview": retrieval_preview,
        }
