# Module 3 — Deterministic Vector Retrieval Engine (RAG)

> **Input**: `ProcessedQuery` (informational tier only)
> **Output**: Answer card with evidence OR fallback escalation signal
> **Location**: `src/retrieval/`

---

## Responsibility

Retrieve the most relevant document chunks from Qdrant, verify that retrieval confidence meets the threshold, synthesize a grounded answer, and return either an **Authoritative Resolution Card** or a **Fallback Signal** — never a guess.

---

## Pipeline

```
ProcessedQuery
    │
    ▼
┌─────────────────────────────────────────┐
│  1. ENCODE QUERY                        │
│  BAAI/bge-small-en-v1.5 → 384-dim vec  │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  2. QDRANT SEARCH                       │
│  Collections selected by query context  │
│  Mandatory filter:                      │
│    status = active                      │
│    approved = true                      │
│    (valid_until filter via nightly sweep)│
│  top_k = 5, score_threshold = 0.82*    │
└─────────────────┬───────────────────────┘
                  │
          Results? │ No results above threshold?
            ┌─────┘──────┐
           YES            NO
            │             │
            ▼             ▼
┌───────────────┐    ┌──────────────┐
│  3. LLM       │    │  FALLBACK    │
│  SYNTHESIS    │    │  Return      │
│  (grounded    │    │  escalation  │
│  answer only) │    │  signal      │
└───────┬───────┘    └──────────────┘
        │
        ▼
┌───────────────────────────────┐
│  4. ANSWER CARD               │
│  answer_text                  │
│  retrieval_score (highest)    │
│  source_chunks (with links)   │
│  valid_from / valid_until     │
└───────────────────────────────┘

* Score threshold configurable in config/rag_config.yaml
```

---

## Confidence Threshold Policy

> **The 0.82 threshold is a starting hypothesis — not a calibrated probability.**

### Before Going Live

1. Build a labelled evaluation set: ~100 student questions with known correct answers mapped to specific document chunks.
2. Run retrieval at thresholds: 0.70, 0.75, 0.80, 0.82, 0.85, 0.90.
3. For each threshold, measure:
   - **Precision**: Of answers returned, what fraction were correct?
   - **Recall**: Of questions with a known answer in the KB, what fraction were correctly returned?
   - **False deflection rate**: Correct answers presented when the source didn't actually support the claim.
   - **Escalation rate**: What fraction of answerable questions were sent to a human?
4. Choose the threshold that minimizes false deflections while keeping escalation rate acceptable (target: < 30% escalation on informational queries).

The threshold is stored in `config/rag_config.yaml`:

```yaml
rag:
  confidence_threshold: 0.82   # Initial hypothesis — must be calibrated
  top_k: 5
  max_answer_tokens: 300
  embedding_model: "BAAI/bge-small-en-v1.5"
  collections:
    - knowledge_circulars
    - knowledge_policies
    - knowledge_faqs
    - knowledge_academic_calendar
    - knowledge_syllabi
    - knowledge_placement
    - knowledge_hostel
    - knowledge_general
```

---

## LLM Synthesis (Answer Generation)

The LLM receives **only** the retrieved chunks as context. It is not given access to parametric knowledge.

### System Prompt (Immutable)

```
You are an administrative information assistant for Lovely Professional University.
Your sole function is to answer student questions using ONLY the document excerpts provided below.

Rules you must always follow:
1. Answer ONLY from the provided excerpts. Do not use any knowledge from your training.
2. If the excerpts do not contain a complete answer, say: "The provided documents do not contain a complete answer to your question. Please contact the relevant department."
3. Always cite the source document by name.
4. Keep answers concise (under 200 words).
5. Never speculate, estimate, or add information not in the excerpts.
6. If the excerpts contain contradictory information, flag the contradiction and do not answer.
```

### User Prompt Template

```
Student question: {normalized_query}

Retrieved document excerpts:
{for each chunk: "[Source: {document_title}, valid {valid_from}–{valid_until}]\n{chunk_text}\n\n"}

Answer based only on the above excerpts:
```

---

## Evidence-Backed Answer Card

Every answer card returned to the student must include:

```python
@dataclass
class AnswerCard:
    answer_text: str                # LLM-generated, grounded in chunks
    retrieval_score: float          # Highest cosine similarity score
    threshold_met: bool
    sources: list[SourceCitation]
    response_latency_ms: int

@dataclass
class SourceCitation:
    document_title: str
    excerpt: str                    # ≤ 400 chars of the most relevant chunk
    source_url: str                 # Original document URL
    drive_url: str                  # Google Drive direct link
    valid_from: date | None
    valid_until: date | None
```

**Rule**: If `threshold_met = False`, `answer_text` must be None. The system never returns an answer with a score below threshold.

---

## Tests (`tests/unit/test_retrieval.py`)

| Test | Scenario | Expected |
|---|---|---|
| `test_high_confidence_answer` | Query matches a known active document at score > 0.82 | Returns answer card with sources |
| `test_low_confidence_fallback` | Query has no matching document | Returns fallback signal; no answer |
| `test_expired_doc_excluded` | Best match is an expired document | Expired doc not returned; fallback if no other match |
| `test_superseded_doc_excluded` | Best match is superseded | Superseded doc not returned |
| `test_pending_doc_excluded` | Best match is pending_review | Not returned by RAG |
| `test_answer_grounded_in_chunks` | LLM given context that doesn't contain answer | LLM responds with "not found" message |
| `test_source_citation_present` | Valid answer returned | Sources list is non-empty |
| `test_threshold_configurable` | Change threshold in config | Behavior changes accordingly |
