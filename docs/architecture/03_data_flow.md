# Data Flow — SMART-RMS

> All data flows are read-only with respect to student records and the existing LPU RMS database.

---

## 1. Student Query Resolution Flow

```
Student types query
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│ MODULE 1: QUERY PROCESSOR                                     │
│                                                               │
│  1. Strip HTML/special chars, normalize whitespace           │
│  2. Spell correction (edit-distance heuristic)               │
│  3. Acronym expansion:                                        │
│       MTE → Mid-Term Examination                             │
│       ETE → End-Term Examination                             │
│       CA  → Continuous Assessment                            │
│       RP  → Re-appear Exam                                   │
│       UMS → University Management System                     │
│       LPU → Lovely Professional University                   │
│       ... (expandable lookup table)                          │
│  4. NER: extract course codes, faculty names, departments    │
│  5. Return: normalized_text, entities{}, timestamp           │
└────────────────────────┬──────────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────────┐
│ MODULE 2: INTENT ROUTER                                       │
│                                                               │
│  Rule-based classification (no model needed initially):       │
│                                                               │
│  IF entity.faculty_name present AND query asks about         │
│     location/office/hours:                                    │
│       → DIRECTORY tier                                        │
│                                                               │
│  ELIF keywords match transactional pattern:                   │
│       (fee refund, grade change, attendance correction,       │
│        registration dispute, scholarship issue...)            │
│       → TRANSACTIONAL tier                                    │
│                                                               │
│  ELSE                                                         │
│       → INFORMATIONAL tier (default)                         │
│                                                               │
│  Tie-break: lower confidence → TRANSACTIONAL (safer)         │
└────┬───────────────────┬─────────────────────┬───────────────┘
     │                   │                     │
INFORMATIONAL        DIRECTORY          TRANSACTIONAL
     │                   │                     │
     ▼                   ▼                     ▼
┌─────────┐    ┌──────────────────┐   ┌────────────────────────┐
│MODULE 3 │    │   MODULE 4       │   │  RMS TAXONOMY LOOKUP   │
│  RAG    │    │  Faculty SQL     │   │                        │
│ Engine  │    │  SELECT * FROM   │   │  Query rms_taxonomy    │
└────┬────┘    │  faculty WHERE   │   │  schema for category   │
     │         │  name ILIKE '%'  │   │  path and dealing      │
     │         └────────┬─────────┘   │  person assignment     │
     │                  │             └──────────┬─────────────┘
     ▼                  ▼                        ▼
S ≥ threshold?   Faculty Card           Pre-populated ticket form
     │           returned to UI         with correct category path
  YES │ NO                              and dealing person shown
     ▼   ▼                              to student for confirmation
Answer  Ticket
 Card   Form
```

---

## 2. Document Ingestion Flow (Admin Upload or Crawler)

```
Source: Admin upload OR Crawler approved list
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  INTAKE                                                     │
│  - Compute SHA-256                                          │
│  - Check document_index for duplicate hash → skip if found │
│  - Check file signature (magic bytes) matches claimed MIME  │
│  - Reject oversized files (> 50 MB)                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                    status = pending_review
                    Written to PostgreSQL knowledge.documents
                    Original file → Google Drive (raw/ folder)
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  ADMIN REVIEW (Manual step — blocking gate)                 │
│  - Admin sees document in review queue                      │
│  - Verifies: title, category, valid_from, valid_until       │
│  - Sets supersedes_document_id if applicable               │
│  - Approves or rejects                                      │
└──────────────────────────┬──────────────────────────────────┘
                           │ status = approved
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  EXTRACTION PIPELINE                                        │
│  - PyMuPDF / python-docx / openpyxl extract text           │
│  - Language detection (flag non-English for review)        │
│  - Chunk: 512 tokens, 64-token overlap                     │
│  - Attach metadata to each chunk:                          │
│       document_id, chunk_index, source_url,                │
│       valid_from, valid_until, category,                   │
│       approved=true, embedding_model_version               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  EMBEDDING & INDEXING                                       │
│  - BAAI/bge-small-en-v1.5 encodes each chunk               │
│  - Vector + payload upserted to Qdrant collection          │
│  - PostgreSQL knowledge.chunks record created              │
│  - status = active                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. TTL Expiry Flow (Nightly Sweep at 00:30)

```
APScheduler triggers ttl_expiry_sweep
        │
        ▼
SELECT document_id FROM knowledge.documents
  WHERE status = 'active'
  AND valid_until IS NOT NULL
  AND valid_until < NOW()
        │
        ▼
For each expired document:
  UPDATE status = 'expired'
  DELETE Qdrant points WHERE payload.document_id = id
  Log expiry event to analytics.document_events
        │
        ▼
For superseded documents (supersedes_document_id not null and newer doc is active):
  Same flow — move to 'superseded' status
```

---

## 4. Nightly Clustering Flow (02:00 daily)

```
APScheduler triggers nightly_clustering
        │
        ▼
SELECT query_text, query_embedding FROM analytics.query_logs
  WHERE resolution = 'fallback'          -- low confidence or transactional
  AND created_at > NOW() - INTERVAL '24h'
  AND included_in_cluster = false
        │ (if < 10 queries → skip; too few to cluster meaningfully)
        ▼
DBSCAN(eps=0.25, min_samples=3, metric='cosine')
  on query_embedding vectors
        │
        ▼
For each cluster with label ≥ 0:
  - Extract representative queries (nearest to centroid)
  - Compute cluster size and density
  - Label cluster with top TF-IDF terms
  - Insert into analytics.cluster_results
        │
        ▼
Top 5 clusters by size → analytics.top_trends (today's date)
        │
        ▼
Admin dashboard shows:
  - Cluster label (top keywords)
  - Sample queries
  - Count of affected students
  - "Publish canonical answer" button
        │ (Admin action — not automated)
        ▼
Admin writes/approves canonical answer
  → Pushed through Module 5 (TTL Manager) as a new FAQ document
  → Enters ingestion pipeline → status = active in Qdrant
```

---

## 5. Crawler → SMART-RMS Handoff Flow

```
UMS Crawler (read-only, human-authorized session)
        │ DISCOVERY MODE (default)
        ▼
discovery_report.html — no files downloaded
        │
        │ Human reviews report → approves specific URLs
        ▼
DOWNLOAD MODE (must pass --approved-list flag)
        │
        ▼
For each approved URL:
  - Fetch document bytes
  - Verify MIME + file signature
  - Compute SHA-256
  - Upload to Google Drive (raw/ subfolder)
  - Record in data/metadata/document_index.csv
  - Insert into PostgreSQL with status = pending_review
        │
        ▼
→ Standard Admin Review gate (same as manual upload)
→ Standard Extraction → Embedding → Qdrant pipeline
```

---

## 6. Data Stores and Their Roles

| Store | Technology | What it holds |
|---|---|---|
| Primary DB | PostgreSQL | Users, RMS taxonomy, document metadata, faculty directory, analytics, chunk records |
| Vector DB | Qdrant | Document chunk embeddings + payload metadata for filtered retrieval |
| Document Storage | Google Drive | Original raw document bytes (PDFs, DOCX, etc.) |
| Crawler session | Local filesystem (gitignored) | Playwright browser context — never committed |
| Secrets | Local `.secrets/` (gitignored) | Google Drive API credentials |
| Config | `config/*.yaml` | Thresholds, allowlists, model versions — committed |
| Logs | `data/crawler/logs/` | Structured crawl error/skip logs — not committed |
