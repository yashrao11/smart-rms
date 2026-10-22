# SMART-RMS — Project Overview

> **AI-Powered Pre-Ticket Deflection & Grievance-Routing System for University Administration**
> Capstone Project-I (CSE339) — B.Tech 7th Semester, Lovely Professional University

---

## What This Project Is

SMART-RMS is an intelligent layer that sits **between students and the existing LPU RMS ticketing system**. It is not a chatbot. It is a deflection and routing engine that:

1. **Instantly resolves** documented, routine questions from verified university sources — without creating a ticket.
2. **Safely escalates** personal disputes (fees, grades, attendance corrections) to the exact authorized administrator defined by the existing RMS routing structure.
3. **Identifies trends** in unresolved queries and helps administrators publish canonical answers to prevent future tickets.

The existing RMS remains the authority for all unresolved, account-specific, and policy-decision issues. SMART-RMS reproduces the **exact same categorization and routing hierarchy** used by LPU RMS so that every escalation lands in the same queue it would have reached manually.

---

## What Problem It Solves

| Current pain point | How SMART-RMS addresses it |
|---|---|
| 3–4 day resolution for factual questions | Sub-second answer cards from verified institutional documents |
| Identical treatment of simple and complex tickets | Dual-tier routing: informational → RAG engine; transactional → RMS dealing person |
| Stale circulars causing contradictory answers | Document TTL, supersession tracking, and retrieval-time validity filters |
| Staff spending hours on repeated questions | DBSCAN clustering surfaces top-5 recurring unresolved themes for one-click canonical answers |
| Students unable to find faculty offices | Deterministic SQL lookup against verified faculty directory |

---

## Core Principles

- **Human authority is preserved.** Grades, fees, attendance corrections, and policy decisions are routed to authorized humans — never answered by AI.
- **No hallucination.** The system returns a source-backed answer only when retrieval confidence meets a calibrated threshold. Below that threshold, it opens a ticket.
- **Exact RMS parity.** Routing follows the actual LPU RMS category → dealing person mapping, not an invented taxonomy.
- **Documents require admin approval.** Crawled or uploaded documents enter the RAG index only after an administrator reviews and approves them.
- **Credentials are never automated.** The UMS crawler requires human manual login; no credentials are stored in code or chat.

---

## Six Core Modules

| # | Module | Role |
|---|---|---|
| 1 | Data Ingestion & Query Pre-Processing | Normalize text, expand acronyms, extract entities |
| 2 | Dual-Tier Intent & Entity Routing Engine | Classify query as informational, directory, or transactional |
| 3 | Deterministic Vector Retrieval Engine (RAG) | Retrieve evidence-backed answers with confidence guardrail |
| 4 | Faculty Directory & Cabin Lookup | SQL-based spatial and schedule lookup |
| 5 | Dynamic Knowledge Ingestion & TTL Manager | Admin upload portal, validity windows, supersession |
| 6 | Nightly Unsupervised Clustering & Admin Portal | DBSCAN-based trending query surface for admins |

---

## Repository Navigation

| Path | Purpose |
|---|---|
| `README.md` | Project summary and quick-start guide |
| `docs/` | All architecture, design, and phase documentation |
| `docs/architecture/` | System design, tech stack, data flow, deployment |
| `docs/database/` | PostgreSQL schema, Qdrant collections, RMS taxonomy tables |
| `docs/modules/` | Per-module design specifications |
| `docs/crawler/` | UMS document crawler + RMS taxonomy extractor design |
| `docs/phases/` | Eight development phase plans |
| `docs/api/` | FastAPI contract specifications |
| `src/` | Source code (to be built) |
| `tests/` | Unit and integration tests |
| `data/` | Metadata, faculty directory, crawler manifests |
| `config/` | YAML configuration files |

---

## Key Documents

- [System Architecture](./architecture/01_system_architecture.md)
- [Tech Stack Decisions](./architecture/02_tech_stack_decisions.md)
- [Data Flow](./architecture/03_data_flow.md)
- [PostgreSQL Schema](./database/01_postgresql_schema.md)
- [RMS Taxonomy Tables](./database/03_rms_taxonomy_tables.md)
- [RMS Taxonomy Extractor Plan](./crawler/02_rms_taxonomy_extractor.md)
- [Phase 1 — Setup & Architecture](./phases/01_setup_and_architecture.md)

---

## Scope Boundaries

| In scope | Out of scope |
|---|---|
| Informational query deflection | Real-time attendance data feeds |
| Faculty cabin/office-hour lookup | Grade calculation or prediction |
| Ticket routing to correct RMS dealing person | Fee payment processing |
| Document TTL and supersession | Profile or account data modification |
| DBSCAN trending-query dashboard (admin analytics only) | External domain crawling |
| Authorized UMS document discovery (read-only) | Replacing LPU RMS |

> **Attendance monitoring**: The README lists real-time attendance tracking as Objective 6. This subsystem requires an authorized data source and should be implemented only after the core query-resolution engine is validated and only if the capstone evaluator confirms it is mandatory for the current semester.
