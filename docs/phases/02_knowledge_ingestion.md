# Phase 02 — Knowledge Collection & Document Ingestion

> **Goal**: Assemble the initial document corpus, build the ingestion pipeline, and validate document quality before any RAG queries are possible.
> **Deliverable**: Organized corpus with validated metadata + working ingestion pipeline.

---

## Tasks

### 2.1 Document Collection Strategy (Priority Order)

Collect documents from **authorized, official sources only**.

| Priority | Source | Document types |
|---|---|---|
| 1 | Official LPU public website (lpu.in) | Academic calendars, syllabi, policies |
| 2 | Admin/mentor-provided exports from RMS | FAQs, circulars, official notices |
| 3 | Authorized UMS sections (post-authorization) | Exam schedules, placement notices |
| 4 | Official department notice boards (physical or portal) | Circulars, hostel guidelines |

**Do not collect from**: Student forums, unofficial websites, third-party compilations, social media.

### 2.2 Target Document Categories (Initial Corpus)

Aim for at least 5–10 documents per category before testing retrieval:

| Category | Examples | Target count |
|---|---|---|
| `circulars` | Administrative notices, policy updates | 10+ |
| `academic_calendar` | Term dates, holiday lists, exam windows | 5+ |
| `exam_schedule` | MTE/ETE timetables | 5+ |
| `faqs` | Manually written Q&A pairs | 20+ |
| `policies` | Fee structure, attendance policy, re-appear rules | 10+ |
| `syllabi` | Course syllabi for common programs | 5+ |
| `placement` | Company visit notices, eligibility criteria | 5+ |
| `hostel` | Hostel rules, warden notices | 5+ |

### 2.3 Manual FAQ Creation

Since crawled documents alone may not cover all common questions, create a base FAQ set manually:

**Process**:
1. Compile the 50 most-asked questions from available sources (student forums, helpdesk logs if accessible, academic administration).
2. Write verified answers with explicit references to official sources.
3. Format as plain text or DOCX: `Q: ... \n A: ...`
4. Ingest through Module 5 as `category = faqs`

This ensures the RAG engine has immediate coverage even before crawler documents are approved.

### 2.4 Build the Ingestion Pipeline

Implement `src/ttl_manager/extractor.py` and supporting components:

- [ ] PDF text extraction (PyMuPDF)
- [ ] DOCX extraction (python-docx)
- [ ] XLSX extraction (openpyxl)
- [ ] PPTX extraction (python-pptx)
- [ ] OCR fallback (pytesseract — only for failed text extraction)
- [ ] Token-aware chunking (512 tokens, 64-token overlap)
- [ ] Metadata attachment to each chunk
- [ ] Qdrant upsert with payload

### 2.5 Document Index Initialization

Create `data/metadata/document_index.csv` with header row:

```csv
document_id,filename,drive_file_id,drive_url,title,category,source_url,publication_date,valid_from,valid_until,status,supersedes_document_id,downloaded_at,uploaded_at,sha256,content_type,file_size_bytes,embedding_model_version,admin_approved_by,admin_approved_at,extraction_quality,crawl_run_id,verification_notes
```

### 2.6 Deduplication Check

Before adding any document:

1. Compute SHA-256 of file bytes
2. Check `document_index.csv` and PostgreSQL for existing SHA-256
3. If duplicate: log as duplicate, update source URL list, do not re-ingest

### 2.7 Extraction Quality Validation

After extracting text from each document:

| Check | Threshold | Action if fails |
|---|---|---|
| Extracted text length | > 50 characters | Try OCR; if still fails → `extraction_quality = failed`; admin notified |
| Language detection | English (or expected language) | Flag for review; do not auto-ingest foreign-language docs |
| Encoding detection | UTF-8 or detected encoding | Re-encode; flag if uncertain |

---

## Definition of Done for Phase 2

- [ ] Ingestion pipeline processes PDF, DOCX, XLSX, PPTX without errors
- [ ] At least 50 documents ingested across all categories
- [ ] All ingested documents have `status = active` in PostgreSQL
- [ ] All Qdrant collections contain at least 1 point
- [ ] SHA-256 deduplication prevents any duplicate from being ingested
- [ ] `document_index.csv` accurately reflects all ingested documents
- [ ] At least one end-to-end retrieval test passes: query → Qdrant → chunk returned
- [ ] TTL expiry test: manually set a past `valid_until` date and verify the document is swept out of Qdrant
