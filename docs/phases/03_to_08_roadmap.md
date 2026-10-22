# Phases 03–08 — Development Roadmap Summary

> For detailed per-phase documentation, see individual phase files. This document provides overview summaries for Phases 3–8.

---

## Phase 03 — Query Processing & Intelligent Routing

**Deliverable**: A tested query-routing engine that correctly classifies informational, directory, and transactional queries.

### Key Tasks
- Implement `src/preprocessing/` (Module 1): normalizer, acronym expander, NER, spell corrector
- Implement `src/intent_router/` (Module 2): rule-based tier classification + RMS path suggester
- Build `config/acronyms.yaml` with known LPU acronyms
- Build the SQL-based RMS path lookup (requires RMS taxonomy in PostgreSQL first)
- Write and pass all unit tests for both modules

### Definition of Done
- [ ] 20+ test queries correctly classified across all three tiers
- [ ] Acronym expansion working for all entries in `acronyms.yaml`
- [ ] Faculty name entity extraction working on test queries
- [ ] Transactional queries return a non-null RMS category path (once taxonomy is loaded)
- [ ] Processing latency < 100ms for 95th percentile on test machine

---

## Phase 04 — RAG Retrieval Engine

**Deliverable**: A working retrieval engine with answer cards, source links, and safe low-confidence fallback.

### Key Tasks
- Implement `src/retrieval/` (Module 3): embedding, Qdrant search, confidence check, LLM synthesis
- Set up local LLM via Ollama (`llama3.2:3b` or similar)
- Build labelled evaluation set (minimum 50 question/answer pairs)
- Empirically evaluate confidence threshold at 0.70, 0.75, 0.80, 0.82, 0.85
- Choose and document the final threshold with precision/recall data

### Definition of Done
- [ ] Full retrieval pipeline works end-to-end: query → embedding → Qdrant → LLM → answer card
- [ ] Expired and superseded documents are never returned
- [ ] System refuses to answer (fallback) when no chunk meets the threshold
- [ ] LLM answer always cites at least one source chunk
- [ ] Evaluation set measured: precision and fallback rate documented
- [ ] p95 latency for full RAG pipeline < 2000ms

---

## Phase 05 — Backend APIs & Student Interface

**Deliverable**: Student can ask a question, receive a verified answer or proceed through ticket creation.

### Key Tasks
- Build FastAPI routes: `/query/resolve`, `/faculty/lookup`, `/tickets/create`, `/query/suggestions`
- Connect frontend React app to backend
- Implement autocomplete suggestions (based on query history / FAQ titles)
- Build faculty directory search UI component
- Build ticket creation form with pre-filled RMS category path
- Build answer card UI component with source citation display
- Rate limiting middleware

### Definition of Done
- [ ] Student UI functional: query input → answer card or ticket form
- [ ] Faculty lookup working via UI with fuzzy matching
- [ ] Pre-filled ticket form shows correct dealing person from taxonomy
- [ ] Source citations display with clickable document links
- [ ] 50 concurrent requests handled without degradation (locust test)

---

## Phase 06 — Admin Portal & Knowledge Lifecycle

**Deliverable**: End-to-end content management workflow without manual application rebuilds.

### Key Tasks
- Build admin JWT authentication (login, refresh, role-based access)
- Build document review queue UI (pending documents with approve/reject actions)
- Build document upload form (drag-and-drop, metadata fields, TTL dates)
- Build faculty directory management (add, edit, deactivate records)
- Build document supersession workflow
- Build audit log viewer
- Connect approval actions to Module 5 extraction pipeline

### Definition of Done
- [ ] Admin can log in and see review queue
- [ ] Admin can approve a document → it appears in Qdrant within 60 seconds
- [ ] Admin can reject a document → it is removed from review queue
- [ ] Admin can upload a new document → standard intake pipeline runs
- [ ] Admin can supersede Document A with Document B → A becomes `superseded` in PostgreSQL and removed from Qdrant
- [ ] All admin actions recorded in audit log

---

## Phase 07 — Trending Query Analytics

**Deliverable**: Nightly clustering pipeline and functional top-5 trends dashboard.

### Key Tasks
- Implement `src/clustering/` (Module 6): DBSCAN + HDBSCAN fallback + TF-IDF labelling
- Schedule via APScheduler at 02:00 daily
- Build admin trends dashboard UI: cluster cards with keywords, sample queries, count, publish button
- Implement canonical answer publish flow → Module 5 intake → admin review

### Definition of Done
- [ ] Clustering job runs at 02:00 without manual trigger
- [ ] After 50+ fallback queries, at least 1 cluster appears on dashboard
- [ ] Admin can click "Publish Answer" → FAQ enters pending_review queue
- [ ] Published FAQs are retrievable by the RAG engine after approval

---

## Phase 08 — Evaluation, Security & Deployment

**Deliverable**: Tested, deployed system with measured results and reproducible demo.

### Key Tasks

**Evaluation**:
- Retrieval accuracy: precision@5 on labelled evaluation set
- Stale document rejection: 100% expired docs excluded (automated test)
- Routing accuracy: 20 manually labelled transactional queries → correct dealing person
- Ticket creation: end-to-end ticket submission tested in RMS (if authorized)
- Deflection rate: % of informational queries answered without escalation (target: ≥ 70%)
- p95 latency: full pipeline under load

**Security**:
- All secrets in `.env` (gitignored) — no hardcoded values anywhere
- JWT expiry enforced; admin sessions expire after 60 minutes
- Admin routes require correct role; reviewer cannot approve documents
- SQL queries use parameterized inputs (no string concatenation)
- File upload: MIME check, size limit, filename sanitization enforced
- No student PII stored beyond session_id in query logs

**Deployment**:
- `docker-compose.yml` starts all services with `docker compose up -d`
- `.env.example` documents all required variables
- `README.md` Quick Start guide updated with real instructions
- Database migrations run automatically on startup via Alembic

### Definition of Done
- [ ] Evaluation report created (see `docs/evaluation_report.md`)
- [ ] All critical security checks passed (listed above)
- [ ] `docker compose up` works from a fresh clone with only `.env` configuration
- [ ] Live demo walkthrough: query → answer card → ticket form → admin review → publish FAQ
- [ ] No hardcoded credentials in any committed file
- [ ] All 3 main user flows documented in `docs/demo_guide.md`

---

## Evaluation Metrics Summary

| Metric | Target | Measurement method |
|---|---|---|
| Query deflection rate | ≥ 70% of informational queries | Counted on evaluation set |
| Retrieval precision@5 | To be set after calibration | Labelled evaluation set |
| Stale document rejection | 100% | Automated test at TTL boundary |
| Ticket routing accuracy | 100% match to RMS taxonomy | 20-query manual test set |
| p95 response latency | < 2000ms | Locust load test |
| Citation correctness | Each answer has ≥ 1 valid source | Manual spot-check of 20 answers |
| False deflection rate | < 5% | Labelled evaluation set |
| Concurrent users | ≥ 50 without errors | Locust load test |
