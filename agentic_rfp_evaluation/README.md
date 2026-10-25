# Agentic RFP Evaluation Mini Project

This project implements an AI-assisted supplier evaluation workflow for PDF-based RFP responses.

## Project goal

- Read supplier proposals from PDF files
- Extract key document content
- Score each proposal against active evaluation criteria using an LLM
- Validate and normalize the LLM output
- Calculate weighted scores, peer benchmarks, and PPI
- Rank suppliers using deterministic tie-break rules
- Persist results in SQLite and display them in Streamlit

## Folder structure

```text
agentic_rfp_evaluation/
├── app.py
├── main.py
├── requirements.txt
├── README.md
├── .gitignore
├── agents/
│   ├── __init__.py
│   └── orchestrator.py
├── config/
│   ├── __init__.py
│   └── settings.py
├── database/
│   ├── schema.sql
│   └── seed_data.sql
├── models/
│   ├── __init__.py
│   └── scorecard.py
├── tools/
│   ├── __init__.py
│   ├── document_tool.py
│   ├── validation_tool.py
│   └── ranking_tool.py
├── uploads/
├── output/
└── data/
```

## Setup

```bash
cd agentic_rfp_evaluation
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
streamlit run app.py
```

## Database

The SQLite schema is stored in `database/schema.sql`, and sample criteria can be loaded from `database/seed_data.sql`.

## Notes

This is a working starter scaffold for the mini project. It is designed to be extended with:

- real PDF upload handling in Streamlit
- LLM-based score generation
- validation and normalization of JSON output
- deterministic ranking logic
- persistent SQLite storage

## Next steps

1. Add full supplier upload flow in `app.py`
2. Connect an LLM provider for score generation
3. Implement the validation pipeline
4. Add benchmark and ranking calculations
5. Save run data and export JSON downloads
