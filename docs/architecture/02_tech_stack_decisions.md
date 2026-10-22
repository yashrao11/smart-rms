# Tech Stack Decisions — SMART-RMS

> **Status**: Locked — agreed on 2026-10-22

---

## Decision Log

All technology choices are recorded here with rationale. If a choice changes, this file is updated with the reason.

---

## 1. Frontend — React.js + Tailwind CSS

**Decision**: React.js with Tailwind CSS utility classes.

**Rationale**:
- Component-based architecture maps cleanly onto the query interface, answer-card, ticket-form, and admin-portal views.
- Tailwind CSS enables rapid, consistent UI development without writing custom CSS for every component.
- Large ecosystem; team familiarity.

**Alternatives considered**:
- Vanilla HTML/JS: Faster to bootstrap, but harder to maintain as the admin portal and dashboard grow.
- Next.js: Adds SSR complexity not needed for an internal university tool.

**Constraints**:
- The student query interface must be keyboard-accessible.
- The admin dashboard must render cluster visualizations without a heavy visualization library — D3.js or Recharts is acceptable.

---

## 2. Backend — Python + FastAPI

**Decision**: Python 3.11+ with FastAPI.

**Rationale**:
- All ML/NLP dependencies (Sentence-Transformers, Scikit-learn, spaCy) are Python-native.
- FastAPI provides async request handling, automatic OpenAPI documentation, and Pydantic validation out of the box.
- Avoids a polyglot stack split (Node.js backend was listed as an alternative in the README; it is excluded here).

**Key libraries**:

| Library | Purpose |
|---|---|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `pydantic` v2 | Request/response validation |
| `sqlalchemy` | ORM for PostgreSQL |
| `alembic` | Database migrations |
| `asyncpg` | Async PostgreSQL driver |
| `httpx` | Async HTTP client for inter-service calls |
| `python-jose` | JWT handling |
| `passlib` | Password hashing (admin accounts only) |
| `apscheduler` | Nightly clustering jobs |

---

## 3. Main Database — PostgreSQL

**Decision**: PostgreSQL 16.

**Rationale**:
- Relational integrity for the RMS taxonomy hierarchy (self-referencing `taxonomy_nodes` table with foreign keys).
- JSON column support for flexible metadata without schema migration for every new field.
- `pgvector` extension available as a fallback if Qdrant is unavailable, avoiding a complete architectural change.
- Production-grade; scales to the university's operational load.

**Schema areas**:
- `rms_taxonomy` schema: Message types, taxonomy nodes, dealing persons, routing assignments.
- `knowledge` schema: Document metadata, chunks, TTL, supersession.
- `faculty` schema: Faculty directory and cabin assignments.
- `analytics` schema: Ticket logs, cluster results, trend summaries.
- `auth` schema: Admin accounts and roles.

**Migration strategy**: Alembic with version-numbered migration scripts in `src/db/migrations/`.

---

## 4. Vector Database — Qdrant

**Decision**: Qdrant (self-hosted via Docker).

**Rationale**:
- Native payload filtering — allows filtering document chunks by `valid_until`, `status`, `category`, and `approved` flag at query time without post-processing.
- Named collections per document category (circulars, policies, FAQs, etc.) allow targeted retrieval.
- REST and Python client both well-maintained.
- Avoids embedding vectors in PostgreSQL, keeping operational data and semantic retrieval concerns separated.

**Why not ChromaDB**: ChromaDB is simpler for prototyping but has weaker filtering semantics at query time. Qdrant's payload filters are essential for TTL enforcement.

**Why not pgvector**: pgvector would add vector retrieval to PostgreSQL. This works, but combining semantic search load and relational query load on the same database is a scaling risk. Qdrant as a dedicated service is cleaner.

**Collections design**: Defined in `docs/database/02_qdrant_collections.md`.

---

## 5. Embeddings — BAAI/bge-small-en-v1.5

**Decision**: Start with `BAAI/bge-small-en-v1.5` via Sentence-Transformers.

**Rationale**:
- 33M parameters; runs on CPU; fast inference (< 50ms per query on standard hardware).
- Strong performance on retrieval benchmarks (MTEB) for English institutional text.
- Produces 384-dimensional vectors; compact for Qdrant storage.

**Migration path**: If retrieval quality is insufficient on real documents, upgrade to `BAAI/bge-base-en-v1.5` (768-dim) or a multilingual model if Hindi/Punjabi queries are common. This change requires re-embedding all documents — the embedding model version is recorded in the document metadata table.

**Do not use**: OpenAI `text-embedding-ada-002` for the initial capstone — it introduces external API dependency and per-query cost. Keep the core retrieval local.

---

## 6. Answer Generation — LLM via Replaceable Interface

**Decision**: Define a `LLMProvider` abstract interface. Initially wire to a locally-run model (Ollama + `llama3.2:3b` or similar). The interface can be swapped to OpenAI, Gemini, or another provider without changing the retrieval pipeline.

**Critical constraint**: The LLM **only synthesizes an answer from retrieved chunks**. It does not use parametric knowledge. The system prompt enforces this.

```
System prompt (non-negotiable):
"You are an administrative assistant for Lovely Professional University.
Answer the student's question using ONLY the following retrieved document excerpts.
Do not use any information outside these excerpts. If the excerpts do not
contain a complete answer, say so explicitly and do not guess."
```

**Evaluation**: The LLM layer is tested with retrieved chunks that are known to contain the answer versus chunks that do not. The system must refuse to answer (trigger fallback) when evidence is absent.

---

## 7. Document Processing

| Library | Purpose |
|---|---|
| `PyMuPDF` (fitz) | PDF text extraction; layout-aware; faster than PyPDF2 |
| `python-docx` | DOCX text and table extraction |
| `openpyxl` | XLSX reading for structured data (e.g., exam timetables) |
| `python-pptx` | PPTX slide text extraction |
| `pytesseract` + `Pillow` | OCR for scanned PDFs (used only when text extraction fails) |
| `chardet` | Encoding detection for plain-text files |
| `langdetect` | Language detection; flag non-English documents for review |

**Chunking strategy**: 512 tokens per chunk, 64-token overlap, using `tiktoken` for token counting. Each chunk carries: `document_id`, `chunk_index`, `source_url`, `valid_from`, `valid_until`, `category`, `approved`.

---

## 8. Clustering — Scikit-learn DBSCAN

**Decision**: `sklearn.cluster.DBSCAN` with cosine distance on query embeddings.

**Rationale**:
- DBSCAN does not require pre-specifying the number of clusters.
- Handles noise (singleton queries) without forcing them into a cluster.
- Runs nightly on the previous 24 hours of unresolved-query embeddings — data volume is small enough for CPU execution.

**Parameters**: `eps` and `min_samples` are stored in `config/clustering_config.yaml` and tuned empirically once real query data is available. Initial values: `eps=0.25`, `min_samples=3`.

**Fallback**: If DBSCAN produces zero meaningful clusters (all noise), HDBSCAN is the documented fallback. HDBSCAN is more robust to varying density but adds a dependency. Include `hdbscan` in `requirements.txt` from the start.

---

## 9. Scheduled Jobs — APScheduler

**Decision**: `APScheduler` with `AsyncIOScheduler`.

**Rationale**:
- Runs inside the FastAPI process without a separate worker service (Celery would require Redis and is overkill for nightly clustering).
- Supports cron-style scheduling for the nightly 02:00 clustering job.
- Can be migrated to Celery Beat if the task volume grows.

**Scheduled jobs**:

| Job | Schedule | Description |
|---|---|---|
| `nightly_clustering` | 02:00 daily | Embed unresolved logs, DBSCAN, update top-5 table |
| `ttl_expiry_sweep` | 00:30 daily | Mark documents past `valid_until` as `expired` in PostgreSQL and remove from Qdrant |
| `drive_sync_check` | 06:00 daily | Check Google Drive for new documents pending admin review |

---

## 10. Crawler — Playwright (Python)

**Decision**: `playwright` Python library with Chromium browser.

**Rationale**:
- UMS is a JavaScript SPA; only a real browser can render and interact with its dropdown-dependent forms.
- Playwright supports saving and restoring browser context (cookies + local storage) — enabling human-authenticated sessions to be reused without automating login.
- Read-only operation; no form submissions.

**Session safety**:
- Session stored in `.playwright_session/` — listed in `.gitignore`.
- Credentials never pass through code; human logs in manually in the visible browser.

---

## 11. Testing — Pytest

**Decision**: Pytest with `pytest-asyncio` and `httpx.AsyncClient` for API tests.

**Test categories**:

| Type | Tool | Scope |
|---|---|---|
| Unit | Pytest | Each module function in isolation |
| Integration | Pytest + AsyncClient | FastAPI routes end-to-end |
| Retrieval accuracy | Custom eval harness | Labelled Q&A set against Qdrant |
| Crawler safety | Pytest | Allowlist, filename sanitization, MIME detection |
| Load | `locust` | Concurrent request handling before demo |

---

## 12. Deployment — Docker Compose

**Decision**: Docker Compose for development and capstone demo. Production-grade Kubernetes is out of scope.

**Services**:

```yaml
services:
  frontend:     # React build served by nginx
  backend:      # FastAPI + uvicorn
  postgres:     # PostgreSQL 16
  qdrant:       # Qdrant vector DB
  # crawler is run manually, not as a daemon service
```

**Environment variables**: Stored in `.env` (gitignored). An `.env.example` with placeholder values is committed.
