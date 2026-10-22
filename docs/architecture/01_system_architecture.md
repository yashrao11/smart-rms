# System Architecture — SMART-RMS

> **Version**: 1.0 (pre-implementation)
> **Status**: Approved design — no code built yet

---

## 1. Architectural Philosophy

SMART-RMS is a **modular, layered deflection system** — not a monolithic chatbot. Each module has a single responsibility, a clear input/output contract, and can be tested independently. The system deliberately preserves human authority over every decision that affects individual student records or policy.

Three hard constraints govern every architectural decision:

1. **Read-before-write**: The system reads verified institutional data. It never writes to student records, grades, fees, or the existing LPU RMS database.
2. **Confidence before answer**: The RAG engine returns an answer only when retrieval evidence meets a calibrated threshold. Otherwise it routes to the correct human.
3. **RMS parity**: Every escalation path mirrors the actual LPU RMS category → dealing-person hierarchy. There is no invented routing logic.

---

## 2. High-Level Component Map

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            SMART-RMS SYSTEM                                  │
│                                                                              │
│  ┌─────────────┐    ┌──────────────────────────────────────────────────┐    │
│  │  STUDENT UI  │───▶│             MODULE 1: QUERY PROCESSOR            │    │
│  │  (React.js) │    │  Normalize · Acronym expansion · NER extraction  │    │
│  └─────────────┘    └──────────────────┬───────────────────────────────┘    │
│                                        │ Structured query + entities         │
│                             ┌──────────▼──────────────┐                     │
│                             │   MODULE 2: INTENT ROUTER│                     │
│                             │  Informational / Directory│                    │
│                             │  / Transactional          │                    │
│                             └──┬─────────┬──────────┬──┘                    │
│                                │         │          │                        │
│                    Informational│  Faculty│lookup    │Transactional           │
│                                ▼         ▼          ▼                        │
│              ┌─────────────────┐  ┌────────────┐  ┌──────────────────────┐  │
│              │   MODULE 3: RAG  │  │  MODULE 4: │  │  RMS TICKET ROUTING  │  │
│              │  Vector Search  │  │  DIRECTORY │  │  Exact dealing-person │  │
│              │  + Confidence   │  │  SQL Lookup│  │  from RMS taxonomy   │  │
│              │  Guardrail      │  └────────────┘  └──────────────────────┘  │
│              └────────┬────────┘         │                   │              │
│                       │                  │                   │              │
│              S≥thresh │  S<thresh        │                   │              │
│                ┌──────▼──┐  ┌────────────▼┐       ┌─────────▼──────────┐   │
│                │ ANSWER  │  │ TICKET FORM │       │  LPU RMS QUEUE     │   │
│                │  CARD   │  │  + Routing  │       │  (external system) │   │
│                └─────────┘  └─────────────┘       └────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              MODULE 5: TTL MANAGER (Admin Portal)                    │   │
│  │  Upload · Validate · Approve · Set TTL · Supersede · Audit log       │   │
│  └──────────────────────────────┬───────────────────────────────────────┘   │
│                                 │                                            │
│                    ┌────────────▼────────────┐                              │
│                    │    QDRANT VECTOR DB      │                              │
│                    │ Chunks + TTL metadata    │◀── Embeddings                │
│                    └─────────────────────────┘                              │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              MODULE 6: NIGHTLY CLUSTERING (APScheduler)              │   │
│  │  Embed unresolved logs · DBSCAN · Top-5 themes · Admin dashboard     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │        UMS DOCUMENT CRAWLER (Separate, Optional, Authorized)         │   │
│  │  Playwright · Human login · Discovery → Admin review → TTL Manager   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Deployment Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Docker Compose                        │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │
│  │  Frontend  │  │  FastAPI   │  │   APScheduler      │  │
│  │  (React)   │  │  Backend   │  │   (Nightly jobs)   │  │
│  │  :3000     │  │  :8000     │  │   (internal)       │  │
│  └────────────┘  └─────┬──────┘  └────────────────────┘  │
│                        │                                  │
│          ┌─────────────┼─────────────┐                   │
│          ▼             ▼             ▼                    │
│  ┌──────────────┐ ┌─────────┐ ┌───────────────┐         │
│  │  PostgreSQL  │ │ Qdrant  │ │  Google Drive  │         │
│  │  :5432       │ │  :6333  │ │  (docs store) │         │
│  └──────────────┘ └─────────┘ └───────────────┘         │
└──────────────────────────────────────────────────────────┘
```

---

## 4. Module Interaction Contracts

### 4.1 Module 1 → Module 2

```
Input:  raw_query (string, max 2000 chars)
Output: {
  normalized_text: string,
  entities: {
    faculty_names: string[],
    course_codes: string[],
    departments: string[],
    acronyms_expanded: {original: string, expanded: string}[]
  },
  query_language: "en",
  timestamp: ISO8601
}
```

### 4.2 Module 2 → Module 3/4/RMS

```
Input:  normalized query + entities
Output: {
  intent_tier: "informational" | "directory" | "transactional",
  confidence_score: float,         // router's own confidence
  routing_target: "rag" | "directory" | "rms_ticket",
  rms_category_path: {             // populated only for transactional
    message_type: string,
    category_type: string,
    master_category: string,
    category: string,
    subcategory: string | null,
    dealing_person_id: uuid
  } | null
}
```

### 4.3 Module 3 RAG Output

```
{
  answer_text: string,
  retrieval_score: float,          // cosine similarity (0.0–1.0)
  threshold_met: boolean,
  source_chunks: [{
    document_id: uuid,
    chunk_id: uuid,
    excerpt: string,               // ≤400 chars
    source_url: string,
    document_title: string,
    valid_from: date | null,
    valid_until: date | null
  }],
  answer_card_type: "resolution" | "fallback",
  response_latency_ms: int
}
```

---

## 5. Critical Design Decisions

### 5.1 Confidence Threshold (S ≥ 0.82)

The value 0.82 is an **initial working hypothesis** derived from the project specification. It is not a calibrated probability. Before the system is considered reliable:

- A labelled question/answer evaluation set must be built from real institutional documents.
- Precision, recall, and fallback rate must be measured at multiple thresholds.
- The threshold must be tuned to minimize both false deflections (wrong answer presented) and false escalations (correct answer not shown).

The threshold is stored in `config/rag_config.yaml` and is not hardcoded.

### 5.2 RMS Taxonomy Parity

The routing logic for transactional queries must **exactly replicate** the LPU RMS form hierarchy:

```
Message Type → Category Type → Master Category → Category → Subcategory → Dealing Person
```

This hierarchy is extracted by the RMS Taxonomy Extractor (see [crawler/02_rms_taxonomy_extractor.md](../crawler/02_rms_taxonomy_extractor.md)) and stored in the `rms_taxonomy` PostgreSQL schema. SMART-RMS reads from this schema to pre-populate dropdowns and route tickets — it does not invent its own taxonomy.

### 5.3 Document Lifecycle Gate

A document enters the active RAG index only after passing through every gate:

```
Crawler/Upload → pending_review → Admin approves → approved →
  Metadata validation (TTL, category) → Text extraction →
    Quality check → Embedding → Qdrant index → active
```

Documents in `pending_review` or `approved` status are **never** returned by the retrieval engine.

---

## 6. System Boundaries

| Action | Allowed | Blocked |
|---|---|---|
| Retrieve from Qdrant | ✅ | — |
| Query PostgreSQL faculty table | ✅ | — |
| Read RMS taxonomy table | ✅ | — |
| Write to student records | — | ✅ |
| Submit forms on external systems | — | ✅ |
| Bypass authentication | — | ✅ |
| Store credentials in source | — | ✅ |
| Return answer below confidence threshold | — | ✅ |
| Route to dealing person not in RMS taxonomy | — | ✅ |

---

## 7. Non-Functional Requirements

| Attribute | Target | Measurement |
|---|---|---|
| Response latency (p95) | < 2,000 ms | Measured in integration tests |
| Retrieval precision@5 | TBD after calibration | Evaluated on labelled set |
| Stale document rejection | 100% of expired docs filtered | Unit tested at TTL boundary |
| Deflection rate | ≥ 70% of informational queries | Measured in pilot |
| Ticket routing accuracy | 100% match to RMS taxonomy | Verified against extracted hierarchy |
| Concurrent requests | ≥ 50 simultaneous | Load tested before demo |
