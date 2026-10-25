# ============================================================================
# AGENTIC RFP EVALUATION SYSTEM WITH RAG
# Complete Solution - No External Tool Calls Required
# ============================================================================

from typing import Dict, List, Optional, Any
import json
import sqlite3
import os
import uuid
from datetime import datetime
from pathlib import Path
import PyMuPDF
import requests
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict


# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

class ScoreLevel(Enum):
    """LLM scoring scale"""
    POOR = 1
    FAIR = 2
    GOOD = 3
    VERY_GOOD = 4
    EXCELLENT = 5


class CriterionType(Enum):
    TECHNICAL = "Technical Capability"
    IMPLEMENTATION = "Implementation Plan"
    COMMERCIAL = "Commercial Value"
    SECURITY = "Security & Compliance"
    SUPPORT = "Support & Experience"


@dataclass
class EvaluationCriteria:
    """Evaluation criteria stored in database"""
    criterion_id: int
    name: str
    description: str
    weight: float  # Percentage, total should be 100
    max_score: int
    is_active: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass  
class SupplierResult:
    """Supplier evaluation result"""
    supplier_name: str
    submission_date: str
    experience_rating: float
    absolute_score: float
    ppi: float  # Peer Performance Index
    final_rank: int
    rfp_run_id: str
    result_json: str  # LLM response JSON


@dataclass  
class CriterionScore:
    """Individual criterion score from LLM"""
    criterion_id: int
    name: str
    weight: float
    max_score: int
    supplier_score: int  # 1-5 scale converted to weighted score
    justification: str
    evidence: List[str]


# ============================================================================
# DATABASE MANAGEMENT (SQLite)
# ============================================================================

class RFPDatabaseManager:
    """Handles all SQLite database operations"""
    
    def __init__(self, db_path: str = "rfp_evaluation.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Create and seed the database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Evaluation criteria table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_criteria (
                criterion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                weight REAL DEFAULT 0.0,
                max_score INTEGER DEFAULT 10,
                is_active BOOLEAN DEFAULT 0
            )
        ''')
        
        # RFP runs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rfp_runs (
                rfp_run_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Supplier results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS supplier_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfp_run_id TEXT NOT NULL,
                supplier_name TEXT NOT NULL,
                submission_date DATE NOT NULL,
                experience_rating REAL DEFAULT 0.0,
                absolute_score REAL DEFAULT 0.0,
                ppi REAL DEFAULT 0.0,
                final_rank INTEGER DEFAULT 0,
                result_json TEXT,
                FOREIGN KEY (rfp_run_id) REFERENCES rfp_runs(rfp_run_id),
                UNIQUE (rfp_run_id, supplier_name)
            )
        ''')
        
        # Insert sample criteria if empty
        cursor.execute('SELECT COUNT(*) FROM evaluation_criteria')
        if cursor.fetchone()[0] == 0:
            sample_criteria = [
                ("Technical Capability", "Architecture, integrations, scalability, technical fit", 30.0, 10),
                ("Implementation Plan", "Timeline, milestones, staffing, risk plan", 20.0, 10),
                ("Commercial Value", "Pricing clarity, total cost, assumptions", 20.0, 10),
                ("Security & Compliance", "Controls, certifications, privacy, auditability", 20.0, 10),
                ("Support & Experience", "Support model, similar projects, references", 10.0, 10)
            ]
            
            for name, desc, weight, max_score in sample_criteria:
                cursor.execute('''
                    INSERT INTO evaluation_criteria (name, description, weight, max_score) VALUES (?, ?, ?, ?)
                ''', (name, desc, weight, max_score))
        
        conn.commit()
        conn.close()
    
    def get_active_criteria(self) -> List[EvaluationCriteria]:
        """Retrieve all active criteria"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM evaluation_criteria WHERE is_active = 1
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [EvaluationCriteria(
            criterion_id=row[0], name=row[1], description=row[2],
            weight=row[3], max_score=row[4], is_active=1 if row[5] else 0
        ) for row in rows]
    
    def create_rfp_run(self, supplier_data: List[Dict]) -> str:
        """Create a new RFP run and insert suppliers"""
        rfp_run_id = f"RFP_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Insert RFP run
        cursor.execute('''
            INSERT INTO rfp_runs (rfp_run_id, status) VALUES (?, ?)
        ''', (rfp_run_id, 'in_progress'))
        
        # Insert suppliers
        for supplier in supplier_data:
            cursor.execute('''
                INSERT INTO supplier_results 
                (rfp_run_id, supplier_name, submission_date, experience_rating) 
                VALUES (?, ?, ?, ?)
            ''', (
                rfp_run_id, 
                supplier['supplier_name'],
                supplier.get('submission_date', datetime.now().strftime('%Y-%m-%d')),
                supplier.get('experience_rating', 0.0)
            ))
        
        conn.commit()
        conn.close()
        
        return rfp_run_id
    
    def save_results(self, rfp_run_id: str, results: List[SupplierResult]):
        """Save evaluation results to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for result in results:
            cursor.execute('''
                INSERT INTO supplier_results 
                (rfp_run_id, supplier_name, submission_date, experience_rating, 
                 absolute_score, ppi, final_rank, result_json) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                rfp_run_id, result.supplier_name, result.submission_date,
                result.experience_rating, result.absolute_score,
                round(result.ppi, 4), result.final_rank, result.result_json
            ))
        
        # Update run status
        cursor.execute('''
            UPDATE rfp_runs SET status = 'completed' WHERE rfp_run_id = ?
        ''', (rfp_run_id,))
        
        conn.commit()
        conn.close()


# ============================================================================
# RAG IMPLEMENTATION - RETRIEVAL AUGMENTED GENERATION
# ============================================================================

class CriterionKnowledgeBase:
    """RAG Knowledge Base for criterion scoring guidance"""
    
    def __init__(self):
        # Schema-based knowledge retrieval patterns
        self.knowledge_patterns = {
            "Technical Capability": [
                {"pattern": r"architecture|technology stack|cloud|scalable", 
                 "guidance": ["Assess technical architecture quality and scalability"],
                 "keywords": ["architecture", "integration", "API", "microservices", "cloud-native"]},
                {"pattern": r"security|encryption|compliance|audit", 
                 "guidance": ["Check for security controls and compliance measures"],
                 "keywords": ["ISO 27001", "SOC 2", "encryption", "GDPR", "PCI-DSS"]}
            ],
            "Implementation Plan": [
                {"pattern": r"timeline|schedule|milestone|phases", 
                 "guidance": ["Evaluate timeline feasibility and milestone clarity"],
                 "keywords": ["6 months", "quarterly", "phase 1", "milestone", "Gantt"]},
                {"pattern": r"team|staffing|resources|experts", 
                 "guidance": ["Assess team composition and resource allocation"],
                 "keywords": ["senior", "lead architect", "QA engineer", "developer"]}
            ],
            "Commercial Value": [
                {"pattern": r"price|cost|budget|total|quote", 
                 "guidance": ["Review pricing transparency and cost structure"],
                 "keywords":["$50,000", "fixed price", "per user", "annual license"]},
                {"pattern": r"license|subscription|maintenance", 
                 "guidance": ["Check licensing model and ongoing costs"],
                 "keywords": ["subscription", "SaaS", "perpetual", "maintenance fee"]}
            ],
            "Security & Compliance": [
                {"pattern": r"data privacy|GDPR|encryption|access control", 
                 "guidance": ["Verify security certifications and data protection measures"],
                 "keywords": ["SSL/TLS", "multi-factor authentication", "audit log"]},
                {"pattern": r"certification|ISO|SOC|compliance", 
                 "guidance": ["Look for industry-standard compliance certifications"],
                 "keywords": ["SOC 2 Type II", "ISO 27001", "GDPR compliant"]}
            ],
            "Support & Experience": [
                {"pattern": r"support|SLA|response time|help desk", 
                 "guidance": ["Evaluate support model and response commitments"],
                 "keywords": ["24/7", "2-hour response", "dedicated account manager"]},
                {"pattern": r"reference|case study|previous|client", 
                 "guidance": ["Check for relevant experience references"],
                 "keywords": ["similar project", "reference client", "50+ customers"]}
            ]
        }
        
        # Best practices and scoring guidelines (RAG context)
        self.best_practices = {
            "technical_excellence": [
                "Strong technical proposals should demonstrate clear architecture diagrams",
                "Integration capabilities must be specific to existing systems",
                "Scalability plans should include concrete metrics (e.g., 10x capacity)"
            ],
            "implementation_quality": [
                "Implementation timeline should have defined phases and milestones",
                "Risk mitigation strategies need to be proactive, not reactive",
                "Resource allocation must match project complexity"
            ],
            "pricing_transparency": [
                "Pricing should break down components clearly",
                "Hidden costs should be explicitly stated or avoided",
                "Payment terms and conditions must be clear"
            ]
        }
    
    def retrieve_context(self, criterion_name: str) -> Dict[str, Any]:
        """Retrieve relevant context for a given criterion"""
        
        # Pattern-based retrieval (semantic search simulation)
        pattern_matches = []
        
        if criterion_name in self.knowledge_patterns:
            for pattern in self.knowledge_patterns[criterion_name]:
                match = {
                    "type": "pattern_match",
                    "criterion_type": criterion_name,
                    "patterns_matched": len(pattern["keywords"]),
                    "guidance_text": pattern["guidance"][0] if pattern["guidance"] else "",
                    "relevant_keywords": pattern["keywords"],
                    "confidence_score": 0.85
                }
                pattern_matches.append(match)
        
        # Add best practices context
        practice_context = {}
        for category, practices in self.best_practices.items():
            if criterion_name.lower() in category.lower():
                practice_context[category] = {
                    "practices": practices[:3],  # Top 3 practices
                    "relevance_score": 0.9
                }
        
        return {
            "criterion": criterion_name,
            "pattern_matches": pattern_matches,
            "best_practices": practice_context,
            "total_retrieval_results": len(pattern_matches) + (1 if practice_context else 0),
            "retrieval_timestamp": datetime.now().isoformat()
        }


class RAGRetriever:
    """Core RAG component for document-based retrieval"""
    
    def __init__(self, knowledge_base: CriterionKnowledgeBase):
        self.knowledge_base = knowledge_base
        # Simulated vector store (in production, use FAISS/Chroma)
        self.vector_store = {
            criterion_name: [] 
            for criterion_name in self.knowledge_base.knowledge_patterns.keys()
        }
    
    def create_chunks(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """Split document into semantic chunks"""
        import re
        
        # Split on paragraphs first
        paragraphs = re.split(r'\n\s*\n', text)
        
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk + " " + para) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = para[:chunk_size] + "..."
            else:
                current_chunk += " " + para
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def retrieve_similar_context(self, query: str, k: int = 3) -> List[Dict]:
        """Retrieve top-k similar context from knowledge base"""
        
        # Simulated similarity search based on keywords
        relevant_keywords = set(query.lower().split())
        
        retrieved_results = []
        
        for criterion_type, patterns in self.knowledge_base.knowledge_patterns.items():
            for pattern in patterns:
                pattern_score = 0
                
                for keyword in pattern["keywords"]:
                    if keyword in query.lower() or any(kw in query.lower() for kw in keyword.split()):
                        pattern_score += 1
                
                if pattern_score > 0 and len(relevant_keywords & set(pattern["keywords"])) > 0:
                    retrieved_results.append({
                        "criterion": criterion_type,
                        "pattern_match_count": pattern_score,
                        "guidance": pattern["guidance"][0] if pattern["guidance"] else "",
                        "keywords_matched": [k for k in pattern["keywords"] if k in query.lower()],
                        "similarity_score": min(1.0, pattern_score / len(pattern["keywords"]))
                    })
        
        # Sort by relevance and return top-k
        retrieved_results.sort(key=lambda x: (x["pattern_match_count"], -x["similarity_score"]), reverse=True)
        
        return retrieved_results[:k]


# ============================================================================
# PDF PROCESSING ENGINE
# ============================================================================

class PDFProcessingEngine:
    """Handles PDF text extraction and processing"""
    
    @staticmethod
    def extract_text_from_pdf(pdf_path: str) -> str:
        """Extract clean text from a PDF file"""
        
        try:
            with PyMuPDF.open(pdf_path) as pdf:
                texts = []
                
                for page_num in range(len(pdf.pages)):
                    page = pdf.pages[page_num]
                    page_text = page.get_text("text")
                    
                    # Clean and normalize text
                    cleaned_text = " ".join(page_text.split())
                    texts.append(cleaned_text)
                
                full_text = "\n\n".join(texts)
                
                return {
                    "raw_text": full_text,
                    "page_count": len(pdf.pages),
                    "word_count": len(full_text.split()),
                    "extraction_timestamp": datetime.now().isoformat()
                }
        
        except Exception as e:
            raise ValueError(f"PDF extraction failed: {str(e)}")


# ============================================================================
# LLM SCORING AGENT (RAG-ENHANCED)
# ============================================================================

class RFPScoringAgent:
    """Main agent that combines PDF processing, RAG retrieval, and LLM scoring"""
    
    def __init__(self, database_manager: RFPDatabaseManager):
        self.db = database_manager
        self.knowledge_base = CriterionKnowledgeBase()
        self.retriever = RAGRetriever(self.knowledge_base)
        
        # Simulated LLM response (in production, integrate with actual LLM API)
        self._llm_response_cache = {}  # Cache for deterministic testing
    
    def build_scoring_prompt(
        self, 
        criterion: EvaluationCriteria, 
        supplier_text: str,
        rag_context: Dict[str, Any] = None
    ) -> str:
        """Build comprehensive prompt with RAG-augmented context"""
        
        # Retrieve relevant context using RAG
        if not rag_context and criterion.name in self.knowledge_base.knowledge_patterns:
            rag_context = self.retriever.retrieve_similar_context(
                f"Score {criterion.name}: {supplier_text[:500]}"
            )
        
        # Build prompt template
        prompt = f"""
You are an AI RFP Evaluation Expert. Analyze the supplier proposal text below and score it against this criterion:

CRITERION DETAILS:
- Name: {criterion.name}
- Description: {criterion.description}
- Weight: {criterion.weight}% of total evaluation
- Maximum Score: {criterion.max_score}/10 points

SUPPLIER PROPOSAL TEXT (relevant sections only):
{supplier_text[:2500]}  # Limit text to prevent token overflow

RAG RETRIEVED CONTEXT (best practices and patterns matched):
"""
        
        if rag_context:
            for match in rag_context.get("pattern_matches", []):
                prompt += f"- Pattern Match ({match['pattern_match_count']} keywords): {match['guidance_text']}\n"
            
            for practice, details in rag_context.get("best_practices", {}).items():
                if "practices" in details:
                    prompt += f"\nBest Practices for '{criterion.name}':\n"
                    for p in details["practices"]:
                        prompt += f"  - {p}\n"
        
        prompt += """

SCORING INSTRUCTIONS:
1. Read the supplier proposal carefully and extract relevant evidence
2. Score on a scale of 1-5, then convert to weighted score out of {criterion.max_score}
3. Provide specific justification citing evidence from the document
4. List 2-3 pieces of supporting evidence with page/section references

OUTPUT FORMAT (JSON ONLY):
{{
    "score": <integer>,
    "justification": "<string>",
    "evidence": ["<string>", ...],
    "risk_flags": ["<string>" or []]
}}

Important: Return ONLY valid JSON. Do not include markdown formatting or explanations outside the JSON."""
        
        return prompt
    
    def score_criterion(
        self, 
        criterion: EvaluationCriteria, 
        supplier_text: str,
        simulate_llm_response: bool = True
    ) -> CriterionScore:
        """Score a single criterion using RAG-augmented approach"""
        
        # Retrieve context via RAG
        rag_context = self.knowledge_base.retrieve_context(criterion.name)
        
        # Build prompt with retrieved context
        prompt = self.build_scoring_prompt(
            criterion, supplier_text, rag_context
        )
        
        # Get LLM response (simulated for this solution)
        llm_response = self._get_llm_response(prompt, simulate_llm_response)
        
        return self._parse_and_validate_score(llm_response, criterion)
    
    def _get_llm_response(self, prompt: str, use_cache: bool = True) -> Dict[str, Any]:
        """Simulate LLM response (replace with actual API call in production)"""
        
        # In production, this would call an LLM API like:
        # response = openai.ChatCompletion.create(...)
        
        if not use_cache or prompt not in self._llm_response_cache:
            # Simulated deterministic responses based on supplier name pattern
            simulated_responses = {
                "Apex": {
                    "score": 8, 
                    "justification": "Strong technical architecture with detailed security controls",
                    "evidence": ["Page 2 - Cloud-native microservices approach", "Page 5 - ISO 27001 certification"],
                    "risks": []
                },
                "BrightPath": {
                    "score": 4, 
                    "justification": "Good cost efficiency but limited technical detail and compliance documentation",
                    "evidence": ["Page 1 - Basic architecture overview", "Missing security section"],
                    "risks": ["Insufficient security detail"]
                },
                "NexaWorks": {
                    "score": 7, 
                    "justification": "Balanced approach with strong implementation planning and support model",
                    "evidence": ["Page 3 - Detailed milestone plan", "Page 4 - SLA commitments"],
                    "risks": []
                },
                "Orbit": {
                    "score": 6, 
                    "justification": "Excellent experience references but vague integration approach",
                    "evidence": ["Page 2 - Reference clients list", "Page 5 - Support team structure"],
                    "risks": ["Unclear integration methodology"]
                }
            }
            
            # Fallback to generic response for unknown suppliers
            supplier_key = "Generic"
            for key in simulated_responses:
                if key.lower() in prompt.lower():
                    supplier_key = key
                    break
            
            self._llm_response_cache[prompt] = simulated_responses.get(supplier_key, {
                "score": 5, 
                "justification": "Standard evaluation based on available evidence",
                "evidence": ["Document reviewed"],
                "risks": []
            })
        
        return self._llm_response_cache[prompt]
    
    def _parse_and_validate_score(self, llm_response: Dict[str, Any], criterion: EvaluationCriteria) -> CriterionScore:
        """Parse LLM response and validate against schema"""
        
        # Validate required fields exist
        if not all(k in llm_response for k in ["score", "justification", "evidence"]):
            raise ValueError(f"Invalid LLM response structure. Missing: {set(['score', 'justification', 'evidence']) - set(llm_response.keys())}")
        
        # Validate score range (1-5 scale mapped to max_score)
        raw_score = llm_response.get("score", 5)
        if not isinstance(raw_score, int) or raw_score < 1 or raw_score > 5:
            raise ValueError(f"Score must be integer between 1 and 5, got: {raw_score}")
        
        # Convert to weighted score (max_score is typically 10)
        weighted_score = round((raw_score / 5.0) * criterion.max_score, 2)
        
        return CriterionScore(
            criterion_id=criterion.criterion_id,
            name=criterion.name,
            weight=criterion.weight,
            max_score=criterion.max_score,
            supplier_score=weighted_score,
            justification=llm_response.get("justification", ""),
            evidence=llm_response.get("evidence", [])
        )

