from __future__ import annotations

import json
import hashlib
from datetime import datetime
from io import BytesIO
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from config.settings import settings
from database.db_manager import DatabaseManager
from tools.document_tool import DocumentTool
from tools.chunking import (
    ensure_chunk_embeddings,
    rank_chunks_by_keywords,
    split_into_chunks,
)
from tools.evaluation_agent import CriterionKnowledgeBase, RAGEvaluationAgent
from tools.ranking_tool import RankingTool
from tools.results_assistant import answer_results_question, criterion_anchor, supplier_anchor
from tools.validation_tool import ValidationTool

st.set_page_config(page_title="Agentic RFP Evaluation", page_icon="📊", layout="wide")

st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stApp {
        background: linear-gradient(180deg, #f6f8ff 0%, #f3f6fb 100%);
    }
    [data-testid="stSidebar"] {
        background-color: #0f172a;
        color: white;
    }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] .stButton > button,
    [data-testid="stSidebar"] .stSelectbox label, [data-testid="stSidebar"] .stTextInput label {
        color: white;
    }
    [data-testid="stSidebar"] .stButton > button {
        background: #2563eb;
        border: none;
        color: white;
        border-radius: 0.75rem;
    }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.82);
        border: 1px solid rgba(148,163,184,0.35);
        border-radius: 0.9rem;
        padding: 0.8rem 0.9rem;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.05);
    }
    .panel-box {
        background: rgba(255,255,255,0.9);
        border: 1px solid rgba(148,163,184,0.4);
        border-radius: 1rem;
        padding: 1rem 1.1rem;
        box-shadow: 0 4px 18px rgba(15,23,42,0.04);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def list_pdf_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.pdf"), key=lambda path: path.name.lower())


def render_pdf_viewer(pdf_path: Path) -> None:
    if not pdf_path.exists():
        st.warning(f"PDF not found: {pdf_path.name}")
        return

    try:
        import fitz

        with fitz.open(pdf_path) as doc:
            if not doc:
                st.warning("This PDF could not be opened.")
                return
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            image_bytes = pix.tobytes("png")
            st.image(image_bytes, caption=f"Preview: {pdf_path.name}")
    except Exception:
        st.warning("Image preview is unavailable for this PDF. Use the extracted text and open/download options below.")

    st.link_button("Open PDF in browser", pdf_path.resolve().as_uri(), type="primary")
    st.download_button(
        label="Download PDF",
        data=pdf_path.read_bytes(),
        file_name=pdf_path.name,
        mime="application/pdf",
        use_container_width=True,
    )


def render_mermaid_flowchart(stage_name: str = "idle", use_rag: bool = True) -> None:
    stage_map = {
        "idle": [
            ("A", "Upload PDF", "done"),
            ("B", "Extract text", "pending"),
            ("C", "Retrieve evidence", "pending"),
            ("D", "Score criteria", "pending"),
            ("E", "Validate output", "pending"),
            ("F", "Rank suppliers", "pending"),
            ("G", "Leaderboard", "pending"),
        ],
        "extract": [
            ("A", "Upload PDF", "done"),
            ("B", "Extract text", "active"),
            ("C", "Retrieve evidence", "pending"),
            ("D", "Score criteria", "pending"),
            ("E", "Validate output", "pending"),
            ("F", "Rank suppliers", "pending"),
            ("G", "Leaderboard", "pending"),
        ],
        "retrieve": [
            ("A", "Upload PDF", "done"),
            ("B", "Extract text", "done"),
            ("C", "Retrieve evidence", "active"),
            ("D", "Score criteria", "pending"),
            ("E", "Validate output", "pending"),
            ("F", "Rank suppliers", "pending"),
            ("G", "Leaderboard", "pending"),
        ],
        "score": [
            ("A", "Upload PDF", "done"),
            ("B", "Extract text", "done"),
            ("C", "Retrieve evidence", "done"),
            ("D", "Score criteria", "active"),
            ("E", "Validate output", "pending"),
            ("F", "Rank suppliers", "pending"),
            ("G", "Leaderboard", "pending"),
        ],
        "validate": [
            ("A", "Upload PDF", "done"),
            ("B", "Extract text", "done"),
            ("C", "Retrieve evidence", "done"),
            ("D", "Score criteria", "done"),
            ("E", "Validate output", "active"),
            ("F", "Rank suppliers", "pending"),
            ("G", "Leaderboard", "pending"),
        ],
        "rank": [
            ("A", "Upload PDF", "done"),
            ("B", "Extract text", "done"),
            ("C", "Retrieve evidence", "done"),
            ("D", "Score criteria", "done"),
            ("E", "Validate output", "done"),
            ("F", "Rank suppliers", "active"),
            ("G", "Leaderboard", "pending"),
        ],
        "complete": [
            ("A", "Upload PDF", "done"),
            ("B", "Extract text", "done"),
            ("C", "Retrieve evidence", "done"),
            ("D", "Score criteria", "done"),
            ("E", "Validate output", "done"),
            ("F", "Rank suppliers", "done"),
            ("G", "Leaderboard", "active"),
        ],
    }

    stages = stage_map.get(stage_name, stage_map["idle"])
    if not use_rag:
        stages = [
            (key, "RAG retrieval disabled" if key == "C" else label, "disabled" if key == "C" else status)
            for key, label, status in stages
        ]
    nodes = "\n    ".join(f'{key}["{label}"]:::status_{status}' for key, label, status in stages)
    chart = f"""
    flowchart LR
        {nodes}
        A --> B --> C --> D --> E --> F --> G
        classDef status_done fill:#dcfce7,stroke:#16a34a,color:#14532d,stroke-width:2px;
        classDef status_active fill:#fef3c7,stroke:#f59e0b,color:#78350f,stroke-width:2px;
        classDef status_pending fill:#e2e8f0,stroke:#475569,color:#0f172a,stroke-width:1px;
        classDef status_disabled fill:#f1f5f9,stroke:#94a3b8,color:#64748b,stroke-width:1px,stroke-dasharray: 5 5;
    """

    html = f"""
    <div class="mermaid">{chart}</div>
    <script>
      (function() {{
        const isReady = () => typeof window.mermaid !== 'undefined';
        const render = () => {{
          if (!isReady()) return;
          window.mermaid.initialize({{
            startOnLoad: true,
            theme: 'neutral',
            securityLevel: 'loose',
            flowchart: {{ curve: 'basis', useMaxWidth: true }}
          }});
          window.mermaid.init(undefined, document.querySelectorAll('.mermaid'));
        }};
        if (isReady()) {{ render(); }} else {{
          const script = document.createElement('script');
          script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
          script.onload = render;
          document.head.appendChild(script);
        }}
      }})();
    </script>
    """
    components.html(html, height=420, scrolling=True)


st.title("Agentic RFP Evaluation")
st.caption("Upload supplier PDFs, evaluate against active criteria, and rank the suppliers.")

with st.sidebar:
    st.header("Project controls")
    st.info("This dashboard demonstrates the workflow from PDF extraction through deterministic ranking.")

    st.subheader("LLM settings")
    llm_provider = st.selectbox(
        "Provider",
        ["OpenAI", "Azure OpenAI", "Ollama"],
        index=0,
    )
    provider_defaults = {
        "OpenAI": "https://api.openai.com/v1",
        "Azure OpenAI": "https://<your-resource>.openai.azure.com/openai/deployments/<deployment>",
        "Ollama": "http://localhost:11434",
    }
    model_defaults = {
        "OpenAI": "gpt-4o-mini",
        "Azure OpenAI": "gpt-4o-mini",
        "Ollama": "llama3.1",
    }
    llm_enabled = st.toggle(
        "Use LLM for scoring and results chat",
        value=False,
        help="Enable this to use the selected OpenAI, Azure OpenAI, or Ollama model for evaluation and results Q&A.",
    )
    llm_api_key = st.text_input(
        "API key",
        type="password",
        value="",
        help="Use your OpenAI or Azure key. Ollama does not require a key.",
    )
    llm_api_base = st.text_input(
        "API base URL",
        value=provider_defaults[llm_provider],
        help="Set the API endpoint for the selected provider.",
    )
    llm_model = st.text_input("Model name", value=model_defaults[llm_provider])

    if st.button("Generate sample PDFs", use_container_width=True):
        from scripts.generate_sample_pdfs import generate_sample_pdfs

        generated = generate_sample_pdfs(settings.upload_dir)
        st.session_state["sample_pdf_paths"] = [str(path) for path in generated]
        st.success(f"Created {len(generated)} sample supplier PDFs.")

    if st.button("Reload criteria", use_container_width=True):
        db = DatabaseManager(settings.database_path)
        st.session_state["criteria"] = db.get_active_criteria()
        st.success("Criteria refreshed.")

criteria = st.session_state.get("criteria") or DatabaseManager(settings.database_path).get_active_criteria()
st.session_state["criteria"] = criteria

all_pdf_files = list_pdf_files(settings.upload_dir)

overview_tab, pdf_tab, chunks_tab, evaluation_tab, leaderboard_tab, knowledge_base_tab, database_tab = st.tabs([
    "Overview",
    "PDF Library",
    "Chunks",
    "Evaluation",
    "Leaderboard",
    "Knowledge Base",
    "Database",
])

with overview_tab:
    st.markdown("<div class='panel-box'>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Supplier inputs")
        supplier_name = st.text_input("Supplier name")
        submission_date = st.date_input("Submission date")
        experience_rating = st.slider("Historical experience rating", min_value=1, max_value=10, value=5)
        uploaded_files = st.file_uploader("Upload supplier PDF(s)", type=["pdf"], accept_multiple_files=True)

        if uploaded_files:
            st.success(f"{len(uploaded_files)} PDF file(s) selected in the uploader.")
            for uploaded_file in uploaded_files:
                st.write(f"- {uploaded_file.name}")

    with col2:
        st.subheader("Criteria overview")
        if criteria:
            metrics_cols = st.columns(min(3, len(criteria) or 1))
            for idx, item in enumerate(criteria):
                with metrics_cols[idx % len(metrics_cols)]:
                    st.metric(item["name"], f"{item['weight']}% weight")

    st.markdown("</div>", unsafe_allow_html=True)

with pdf_tab:
    st.subheader("PDF library")
    if all_pdf_files:
        st.caption(f"{len(all_pdf_files)} PDF(s) stored in the project library.")
        pdf_inventory = []
        for pdf_file in all_pdf_files:
            file_stat = pdf_file.stat()
            pdf_inventory.append({
                "File name": pdf_file.name,
                "Size (KB)": round(file_stat.st_size / 1024, 1),
                "Last modified": datetime.fromtimestamp(file_stat.st_mtime),
            })
        st.dataframe(
            pdf_inventory,
            hide_index=True,
            width="stretch",
            column_config={
                "Last modified": st.column_config.DatetimeColumn("Last modified", format="D MMM YYYY, HH:mm"),
            },
            alt="PDF files available in the project library",
        )

        pdf_to_read = st.selectbox(
            "Choose a PDF to preview and read",
            options=[pdf_file.name for pdf_file in all_pdf_files] or ["No PDFs found"],
            index=0,
        )

        if pdf_to_read and pdf_to_read != "No PDFs found":
            selected_pdf_path = settings.upload_dir / pdf_to_read
            if selected_pdf_path.exists():
                preview_col, text_col = st.columns([1.3, 1])

                with preview_col:
                    st.subheader(f"Preview: {pdf_to_read}")
                    render_pdf_viewer(selected_pdf_path)

                with text_col:
                    if st.button("Read selected PDF", use_container_width=True):
                        extracted_text = DocumentTool().extract_text(selected_pdf_path)
                        st.session_state["selected_pdf_text"] = extracted_text

                    if "selected_pdf_text" in st.session_state:
                        extracted_pdf_text = st.session_state["selected_pdf_text"]
                        if extracted_pdf_text.strip():
                            st.text_area(
                                "PDF content",
                                value=extracted_pdf_text,
                                height=760,
                                key="pdf_reader_area",
                            )
                        else:
                            st.warning("This PDF does not contain any readable text. Generate the sample PDFs again to refresh the files.")
                    else:
                        st.info("Click 'Read selected PDF' to extract and display the PDF text.")
    else:
        st.info("No PDFs are available yet. Generate sample PDFs or upload some documents.")

    if st.button("Clear extracted text", use_container_width=True):
        st.session_state.pop("selected_pdf_text", None)

with evaluation_tab:
    st.subheader("Supplier evaluation")

    chunking_enabled = st.toggle(
        "Chunk proposal documents",
        value=True,
        help="Split each extracted proposal into overlapping word windows and retrieve relevant chunks per criterion.",
    )
    if chunking_enabled:
        chunk_col, overlap_col = st.columns(2)
        with chunk_col:
            chunk_size_words = st.number_input("Chunk size (words)", min_value=100, max_value=2000, value=500, step=50)
        with overlap_col:
            overlap_words = st.number_input("Chunk overlap (words)", min_value=0, max_value=int(chunk_size_words) - 1, value=min(80, int(chunk_size_words) - 1), step=10)
        retrieval_mode = st.selectbox("Chunk retrieval method", ["Keyword matching", "Embeddings"], index=0)
        if retrieval_mode == "Embeddings":
            st.caption("Embeddings mode performs cosine nearest-neighbor search in the persistent SQLite-vec index.")
    else:
        chunk_size_words = 500
        overlap_words = 80
        retrieval_mode = "Keyword matching"
        st.caption("Chunking is disabled. Each proposal will be treated as one document chunk.")

    embedding_model = st.text_input(
        "Embedding model / deployment",
        value="nomic-embed-text" if llm_provider == "Ollama" else "text-embedding-3-small",
        help="Only required for Embeddings retrieval. OpenAI/Azure require a key; Ollama requires a locally running model.",
    )
    st.caption("Keyword matching stores proposal text only. Embeddings retrieval indexes vectors once per PDF, chunk configuration, and embedding model.")

    rag_enabled = st.toggle(
        "Enable RAG retrieval",
        value=True,
        help="When enabled, criterion keywords and guidance are matched against proposal text. This is keyword retrieval, not embedding-based vector search.",
    )
    if rag_enabled:
        st.caption("Retrieval mode: criterion keyword matching and guidance")
    else:
        st.caption("Retrieval is off. Scoring still uses proposal evidence heuristics and the selected LLM setting.")

    render_mermaid_flowchart("idle", use_rag=rag_enabled)

    st.write("This workflow processes uploaded proposal PDFs through extraction, retrieval, scoring, validation, and ranking.")

    stage_legend = {
        "completed": "✅ Completed",
        "active": "🟠 Active",
        "pending": "⚪ Pending",
    }
    for label, meaning in stage_legend.items():
        st.caption(f"{meaning} = {label}")

    if st.button("Evaluate suppliers", type="primary", use_container_width=True):
        if not uploaded_files:
            st.warning("Please upload at least one PDF before evaluating.")
        else:
            total_files = len(uploaded_files)
            progress_bar = st.progress(0, text="Evaluation starting...")
            status_text = st.empty()

            db = DatabaseManager(settings.database_path)
            run_id = db.create_run(status="completed")
            validation_tool = ValidationTool()
            ranking_tool = RankingTool()
            llm_config = {
                "provider": llm_provider,
                "enabled": llm_enabled and bool(llm_api_key.strip() or llm_provider == "Ollama"),
                "api_key": llm_api_key.strip(),
                "api_base": llm_api_base.strip() or provider_defaults[llm_provider],
                "model": llm_model.strip() or model_defaults[llm_provider],
            }
            embeddings_retrieval_enabled = (
                rag_enabled
                and retrieval_mode == "Embeddings"
                and (llm_provider.lower() == "ollama" or bool(llm_api_key.strip()))
            )
            if rag_enabled and retrieval_mode == "Embeddings" and not embeddings_retrieval_enabled:
                st.warning("No API key is configured for this provider. Using keyword matching for this evaluation.")

            evaluation_agent = RAGEvaluationAgent(criteria, llm_config=llm_config, use_rag=rag_enabled)
            results = []
            knowledge_base = CriterionKnowledgeBase()

            for idx, uploaded_file in enumerate(uploaded_files, start=1):
                progress_value = (idx - 1) / total_files
                progress_bar.progress(progress_value, text=f"Processing {uploaded_file.name} ({idx}/{total_files})")
                status_text.caption("Step 1/6: extracting text from uploaded proposal")
                render_mermaid_flowchart("extract", use_rag=rag_enabled)
                file_bytes = uploaded_file.getvalue()
                temp_path = settings.upload_dir / uploaded_file.name
                temp_path.write_bytes(file_bytes)

                document_tool = DocumentTool()
                extracted_pages = document_tool.extract_pages(temp_path)
                extracted_text = "\n\n".join(page["text"] for page in extracted_pages if page["text"])

                source_chunks = (
                    split_into_chunks(extracted_pages, int(chunk_size_words), int(overlap_words))
                    if chunking_enabled
                    else split_into_chunks(extracted_pages, max(len(extracted_text.split()), 1), 0)
                )
                document_hash = hashlib.sha256(file_bytes).hexdigest()
                source_name = uploaded_file.name
                retrieval_chunks = [dict(chunk, source_name=source_name) for chunk in source_chunks]
                if embeddings_retrieval_enabled:
                    try:
                        retrieval_chunks, embeddings_reused = ensure_chunk_embeddings(
                            retrieval_chunks,
                            db.get_proposal_chunks(document_hash),
                            embedding_model.strip(),
                            evaluation_agent.create_embeddings,
                        )
                    except Exception as error:
                        st.error(
                            "Could not create proposal embeddings. No chunks were saved for this document. "
                            f"Check the provider, API key or local embedding model, and deployment name. Details: {error}"
                        )
                        st.stop()
                    status_text.caption(
                        "Proposal embeddings reused from SQLite."
                        if embeddings_reused
                        else "Proposal chunks embedded and indexed in SQLite."
                    )
                else:
                    status_text.caption("Proposal text chunks indexed in SQLite without embeddings.")

                effective_retrieval_mode = "embeddings" if embeddings_retrieval_enabled else "keyword"

                db.save_proposal_chunks(
                    document_hash=document_hash,
                    source_name=uploaded_file.name,
                    supplier_name=supplier_name or uploaded_file.name.replace(".pdf", "").replace("_", " ").title(),
                    chunks=retrieval_chunks,
                    embedding_model=embedding_model.strip(),
                )

                retrieved_chunks_by_criterion: dict[str, list[dict[str, object]]] = {}
                if rag_enabled:
                    for criterion in criteria:
                        criterion_name = criterion["name"]
                        pattern = knowledge_base.knowledge_patterns.get(criterion_name, {})
                        keywords = pattern.get("keywords", [])
                        if embeddings_retrieval_enabled:
                            query = " ".join([
                                criterion_name,
                                str(criterion.get("description", "")),
                                str(pattern.get("guidance", "")),
                                " ".join(keywords),
                            ])
                            query_embedding = evaluation_agent.create_embeddings([query], embedding_model.strip())[0]
                            selected_chunks = db.search_similar_chunks(
                                document_hash,
                                embedding_model.strip(),
                                query_embedding,
                                top_k=3,
                            )
                        else:
                            selected_chunks = rank_chunks_by_keywords(retrieval_chunks, keywords, top_k=3)
                        for chunk in selected_chunks:
                            chunk["retrieval_method"] = effective_retrieval_mode
                            if not chunk.get("matched_keywords"):
                                lowered_chunk = str(chunk.get("text", "")).lower()
                                chunk["matched_keywords"] = [keyword for keyword in keywords if keyword.lower() in lowered_chunk]
                        retrieved_chunks_by_criterion[criterion_name] = selected_chunks

                status_text.caption("Step 2/6: retrieving evidence and matching criterion guidance")
                render_mermaid_flowchart("retrieve", use_rag=rag_enabled)

                scorecard = evaluation_agent.score_supplier(
                    supplier_name=supplier_name or uploaded_file.name.replace(".pdf", "").replace("_", " ").title(),
                    pdf_text=extracted_text,
                    submission_date=str(submission_date),
                    experience_rating=float(experience_rating),
                    retrieved_chunks_by_criterion=retrieved_chunks_by_criterion if chunking_enabled else None,
                )

                status_text.caption("Step 3/6: scoring supplier against the criteria")
                render_mermaid_flowchart("score", use_rag=rag_enabled)

                normalized = validation_tool.normalize_result(scorecard)
                valid, warnings = validation_tool.validate_result(normalized)
                if not valid:
                    st.warning(f"Validation issue for {supplier_name or uploaded_file.name}: {warnings[:2]}")

                status_text.caption("Step 4/6: validating normalized scorecard data")
                render_mermaid_flowchart("validate", use_rag=rag_enabled)

                for idx, criterion in enumerate(scorecard.get("criteria", [])):
                    if idx < len(normalized["criteria"]):
                        normalized["criteria"][idx]["name"] = criteria[idx]["name"]
                        normalized["criteria"][idx]["rag_context"] = criterion.get("rag_context", {})
                        normalized["criteria"][idx]["llm_source"] = criterion.get("llm_source", "fallback")
                        normalized["criteria"][idx]["raw_response"] = criterion.get("raw_response", {})

                normalized["warnings"] = warnings
                normalized["llm_raw_response"] = scorecard.get("llm_raw_response", {})
                normalized["retrieval_preview"] = scorecard.get("retrieval_preview", [])
                normalized["absolute_score"] = ranking_tool.calculate_absolute_score(normalized)
                results.append(normalized)

            progress_bar.progress(1.0, text="Finalizing rankings and leaderboard")
            status_text.caption("Step 5/6: ranking suppliers and generating final scorecards")
            render_mermaid_flowchart("rank", use_rag=rag_enabled)

            ranked = ranking_tool.evaluate_run(results)

            status_text.caption("Step 6/6: publishing leaderboard and output summary")
            render_mermaid_flowchart("complete", use_rag=rag_enabled)

            for rank_position, result in enumerate(ranked, start=1):
                db.save_supplier_result(
                    rfp_run_id=run_id,
                    supplier_name=result["supplier_name"],
                    submission_date=result.get("submission_date", str(submission_date)),
                    experience_rating=float(result.get("experience_rating", experience_rating)),
                    absolute_score=float(result.get("absolute_score", 0)),
                    ppi=float(result.get("ppi", 0)),
                    final_rank=int(rank_position),
                    result_json=result,
                    warnings=result.get("warnings", []),
                )

            st.session_state["last_run"] = ranked
            st.session_state["last_run_id"] = run_id
            st.session_state["last_chunk_document_hash"] = document_hash if uploaded_files else None
            st.success(f"Evaluation finished for run ID {run_id}.")

with chunks_tab:
    st.subheader("Proposal chunks")
    db = DatabaseManager(settings.database_path)
    chunk_documents = db.get_chunk_documents()

    if chunk_documents:
        document_labels = {
            f"{item['source_name']} · {item['supplier_name']} · {item['chunk_count']} chunks": item
            for item in chunk_documents
        }
        selected_document_label = st.selectbox(
            "Select a processed proposal",
            options=list(document_labels),
            key="chunk_document_selector",
        )
        selected_document = document_labels[selected_document_label]
        chunks = db.get_proposal_chunks(selected_document["document_hash"])
        st.caption(
            f"{selected_document['source_name']} · {len(chunks)} chunks · "
            f"Embedding model: {selected_document.get('embedding_model') or 'not generated'}"
        )

        for chunk in chunks:
            page_label = (
                f" · pages {chunk['page_start']}–{chunk['page_end']}"
                if chunk.get("page_start")
                else ""
            )
            section_label = " > ".join(chunk.get("section_path", []))
            section_suffix = f" · {section_label}" if section_label else ""
            with st.expander(f"Chunk {chunk['chunk_index'] + 1} · {chunk['word_count']} words{page_label}{section_suffix}"):
                st.text(chunk["text"])
                if chunk.get("embedding_text") and chunk["embedding_text"] != chunk["text"]:
                    st.caption(f"Embedding context: {chunk['embedding_text']}")
                if chunk.get("embedding"):
                    st.caption(f"Embedding dimensions: {len(chunk['embedding'])}")
                else:
                    st.caption("No embedding stored; this chunk was indexed for keyword retrieval.")
    else:
        st.info("No proposal chunks have been created yet. Run an evaluation to chunk and index its uploaded PDFs.")

with leaderboard_tab:
    leaderboard_db = DatabaseManager(settings.database_path)
    saved_runs = [
        run for run in leaderboard_db.get_all_runs()
        if leaderboard_db.get_supplier_results(int(run["rfp_run_id"]))
    ]
    if saved_runs:
        selected_run_id = st.selectbox(
            "Evaluation run",
            options=[int(run["rfp_run_id"]) for run in saved_runs],
            format_func=lambda run_id: next(
                f"Run {run_id} · {run['created_at']}"
                for run in saved_runs
                if int(run["rfp_run_id"]) == run_id
            ),
            key="leaderboard_run_selector",
        )
        saved_rows = leaderboard_db.get_supplier_results(selected_run_id)
        results_for_run = [
            {
                **row["result"],
                "supplier_name": row["supplier_name"],
                "absolute_score": row["absolute_score"],
                "ppi": row["ppi"],
                "final_rank": row["final_rank"],
                "warnings": row["warnings"],
            }
            for row in saved_rows
        ]
        chat_run_key = "results_assistant_run_id"
        if st.session_state.get(chat_run_key) != selected_run_id:
            st.session_state["results_assistant_messages"] = []
            st.session_state[chat_run_key] = selected_run_id

        with st.container(border=True):
            st.subheader("Ask the evaluation assistant", icon=":material/forum:")
            st.caption("Ask about supplier rankings, criterion scores, evidence, or risks. Answers cite the saved scorecards.")
            with st.form("results_assistant_form", clear_on_submit=True):
                question = st.text_input(
                    "Your question",
                    placeholder="For example: Why did North Star rank first?",
                )
                submitted = st.form_submit_button(
                    "Ask assistant",
                    type="primary",
                    icon=":material/send:",
                    width="stretch",
                )
            if submitted:
                if not question.strip():
                    st.warning("Enter a question about this evaluation.")
                else:
                    messages = st.session_state.setdefault("results_assistant_messages", [])
                    messages.append({"role": "user", "content": question.strip()})
                    chat_llm_config = {
                        "provider": llm_provider,
                        "enabled": llm_enabled and bool(llm_api_key.strip() or llm_provider.lower() == "ollama"),
                        "api_key": llm_api_key.strip(),
                        "api_base": llm_api_base.strip() or provider_defaults[llm_provider],
                        "model": llm_model.strip() or model_defaults[llm_provider],
                    }
                    chat_agent = RAGEvaluationAgent(criteria, llm_config=chat_llm_config, use_rag=rag_enabled)
                    if not chat_agent.use_llm:
                        assistant_answer = "LLM chat is not enabled or the provider is missing credentials. Enable LLM use in Project controls, then ask again."
                    else:
                        try:
                            assistant_answer = answer_results_question(
                                question.strip(),
                                results_for_run,
                                llm_chat=chat_agent.generate_chat_response,
                                source_link=lambda source_name, page_number: (
                                    f"{(settings.upload_dir / Path(source_name).name).resolve().as_uri()}#page={page_number}"
                                ),
                            )
                        except Exception as error:
                            assistant_answer = f"I couldn't get an answer from the configured LLM: {error}"
                    messages.append({"role": "assistant", "content": assistant_answer})

            for message in st.session_state.get("results_assistant_messages", []):
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        st.subheader("Leaderboard")
        leaderboard = [{
            "Rank": idx + 1,
            "Supplier": row["supplier_name"],
            "Absolute Score": row.get("absolute_score", 0),
            "PPI": row.get("ppi", 0),
            "Submission Date": row.get("submission_date", "N/A"),
            "Experience": row.get("experience_rating", 0),
        } for idx, row in enumerate(results_for_run)]
        st.dataframe(leaderboard, use_container_width=True)

        for supplier in results_for_run:
            supplier_name = supplier["supplier_name"]
            st.subheader(supplier_name, anchor=supplier_anchor(supplier_name))
            with st.expander(f"View {supplier_name} scorecard"):
                criteria_data = supplier.get("criteria", [])
                for item in criteria_data:
                    criterion_name = str(item.get("name", f"Criterion {item['criterion_id']}"))
                    st.subheader(
                        f"Criterion {item['criterion_id']}: {criterion_name}",
                        anchor=criterion_anchor(supplier_name, criterion_name),
                    )
                    st.markdown(
                        f"**Score:** {item['score']}/{item['max_score']} — {item['justification']}"
                    )
                    rag_context = item.get("rag_context", {})
                    if rag_context:
                        st.caption(f"Matched keywords: {', '.join(rag_context.get('matched_keywords', [])) or 'none'}")
                        st.caption(f"Retrieval guidance: {rag_context.get('guidance', '')}")
                        for retrieved_chunk in rag_context.get("retrieved_chunks", []):
                            st.caption(
                                f"Retrieved chunk {int(retrieved_chunk.get('chunk_index', 0)) + 1} "
                                f"(relevance {retrieved_chunk.get('retrieval_score', 0)}): "
                                f"{retrieved_chunk.get('text', '')}"
                            )
                    st.write(f"Evidence: {item.get('evidence', '')}")

                st.write("Risks:")
                for risk in supplier.get("risks", []):
                    st.write(f"- {risk}")
                st.write(f"Overall summary: {supplier.get('overall_summary', '')}")
                st.write(f"Absolute score: {supplier.get('absolute_score', 0)}")
                st.write(f"PPI: {supplier.get('ppi', 0)}")

                raw_response = supplier.get("llm_raw_response", {})
                if raw_response:
                    st.subheader("LLM evaluation preview")
                    st.json(raw_response)

                retrieval_preview = supplier.get("retrieval_preview", [])
                if retrieval_preview:
                    st.subheader("Per-criterion retrieval snippets")
                    for snippet in retrieval_preview:
                        st.markdown(f"**{snippet.get('criterion', 'Criterion')}**")
                        st.write(snippet.get('guidance', ''))
                        st.write(f"Matched keywords: {', '.join(snippet.get('matched_keywords', [])) or 'none'}")
                        st.write(f"Coverage: {snippet.get('coverage_ratio', 0)}")

                st.write(json.dumps(supplier.get("warnings", []), indent=2))
    else:
        st.info("No evaluation has been run yet. Go to the Evaluation tab to calculate the supplier rankings.")

with knowledge_base_tab:
    st.subheader("Evaluation knowledge base")
    knowledge_base = CriterionKnowledgeBase()
    pattern_records = knowledge_base.knowledge_patterns

    st.caption(
        f"Evaluation criteria are loaded from SQLite at `{settings.database_path}`. "
        "RAG keywords and guidance are currently defined in the application code."
    )

    knowledge_rows = []
    for criterion in criteria:
        pattern = pattern_records.get(criterion["name"], {})
        knowledge_rows.append({
            "ID": criterion["criterion_id"],
            "Criterion": criterion["name"],
            "Description (SQLite)": criterion.get("description", ""),
            "Weight": criterion["weight"],
            "Max score": criterion["max_score"],
            "Active": "Yes" if criterion["is_active"] else "No",
            "RAG keywords": ", ".join(pattern.get("keywords", [])),
            "Retrieval guidance": pattern.get(
                "guidance",
                "Assess the supplier response against the criterion evidence.",
            ),
        })

    if knowledge_rows:
        st.dataframe(knowledge_rows, hide_index=True, width="stretch")

        selected_criterion = st.selectbox(
            "Inspect a criterion",
            options=[row["Criterion"] for row in knowledge_rows],
            key="knowledge_base_criterion",
        )
        selected_row = next(row for row in knowledge_rows if row["Criterion"] == selected_criterion)

        with st.container(border=True):
            st.markdown(f"#### {selected_row['Criterion']}")
            st.write(selected_row["Description (SQLite)"] or "No description is stored for this criterion.")
            st.write(f"**Retrieval keywords:** {selected_row['RAG keywords'] or 'No keyword rules configured.'}")
            st.write(f"**Guidance:** {selected_row['Retrieval guidance']}")
            st.caption(
                f"Weight: {selected_row['Weight']}% · Max score: {selected_row['Max score']} · "
                f"Active: {selected_row['Active']}"
            )
    else:
        st.info("No evaluation criteria are available in SQLite yet.")

with database_tab:
    st.subheader("SQLite database explorer")
    st.caption(f"Read-only connection to `{settings.database_path}`. Queries cannot modify database contents.")
    db = DatabaseManager(settings.database_path)
    tables = db.list_tables()

    if tables:
        table_rows = [{"Table": table["name"], "Rows": table["row_count"], "Columns": len(table["columns"])} for table in tables]
        st.dataframe(table_rows, hide_index=True, width="stretch", alt="SQLite tables and their row and column counts")

        table_by_name = {table["name"]: table for table in tables}
        selected_table_name = st.selectbox(
            "Inspect a table",
            options=list(table_by_name),
            key="database_table_selector",
        )
        selected_table = table_by_name[selected_table_name]

        schema_rows = [{
            "Column": column["name"],
            "Type": column["type"] or "(inferred)",
            "Not null": bool(column["notnull"]),
            "Primary key": bool(column["pk"]),
            "Default": column["dflt_value"],
        } for column in selected_table["columns"]]
        st.markdown(f"**Schema: `{selected_table_name}`**")
        st.dataframe(schema_rows, hide_index=True, width="stretch", alt=f"Column schema for {selected_table_name}")

        if st.button(f"Browse `{selected_table_name}` rows", key="browse_database_table"):
            quoted_table = selected_table_name.replace('"', '""')
            try:
                columns, rows, truncated = db.query_readonly(f'SELECT * FROM "{quoted_table}" LIMIT 100')
                st.session_state["database_query_result"] = (columns, rows, truncated)
                st.session_state["database_query_label"] = f"Rows from {selected_table_name}"
            except Exception as error:
                st.error(f"Could not read table: {error}")

        st.markdown("#### SQL query")
        query_text = st.text_area(
            "Read-only SQL",
            value="SELECT * FROM evaluation_criteria LIMIT 100;",
            height=140,
            help="Run a single SELECT or read-only WITH query. Results are capped at 1,000 rows.",
            key="database_sql_query",
        )
        if st.button("Run query", type="primary", key="run_database_query"):
            try:
                columns, rows, truncated = db.query_readonly(query_text, max_rows=1000)
                st.session_state["database_query_result"] = (columns, rows, truncated)
                st.session_state["database_query_label"] = "SQL query results"
            except Exception as error:
                st.error(f"Query could not be run: {error}")

        if "database_query_result" in st.session_state:
            result_columns, result_rows, was_truncated = st.session_state["database_query_result"]
            st.markdown(f"**{st.session_state.get('database_query_label', 'Query results')}** · {len(result_rows)} rows")
            if result_rows:
                st.dataframe(result_rows, hide_index=True, width="stretch", alt="Read-only SQLite query results")
            else:
                st.info(f"The query returned no rows. Columns: {', '.join(result_columns)}")
            if was_truncated:
                st.caption("Showing the first 1,000 rows. Refine the query with a LIMIT clause to inspect a smaller result.")
    else:
        st.info("No tables found in the configured SQLite database.")
