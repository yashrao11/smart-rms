# PostgreSQL Schema — SMART-RMS

> **Database**: `smart_rms`
> **Version**: 1.0 (pre-implementation)
> **Migration tool**: Alembic

All DDL statements are guides for Alembic migration scripts. Do not run these directly; use `alembic upgrade head`.

---

## Schema Organization

```
smart_rms database
├── rms_taxonomy    — Exact replication of LPU RMS category hierarchy
├── knowledge       — Document metadata, chunks, and TTL management
├── faculty         — Faculty directory and cabin assignments
├── analytics       — Query logs, clusters, and trend results
└── auth            — Admin accounts and roles
```

---

## Schema: `rms_taxonomy`

This schema mirrors the **exact hierarchy** from the LPU RMS form. Do not invent or simplify categories. All values come from the RMS Taxonomy Extractor (see `docs/crawler/02_rms_taxonomy_extractor.md`).

### Table: `rms_taxonomy.message_types`

```sql
CREATE TABLE rms_taxonomy.message_types (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rms_option_id   VARCHAR(64) UNIQUE,          -- Original RMS internal ID if extractable
    label           VARCHAR(255) NOT NULL UNIQUE, -- Exact label from RMS dropdown
    display_order   INTEGER,                      -- Order as it appears in the RMS form
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    extracted_at    TIMESTAMPTZ,                  -- When extracted from UMS by the extractor
    verified_at     TIMESTAMPTZ,                  -- When manually verified by a human
    notes           TEXT,                         -- Ambiguities, discrepancies, manual review notes
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Table: `rms_taxonomy.taxonomy_nodes`

This is a **self-referencing table** that represents the entire dropdown hierarchy:
`Message Type → Category Type → Master Category → Category → Subcategory → (deeper if present)`

```sql
CREATE TABLE rms_taxonomy.taxonomy_nodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_type_id UUID NOT NULL REFERENCES rms_taxonomy.message_types(id),
    parent_id       UUID REFERENCES rms_taxonomy.taxonomy_nodes(id), -- NULL for top-level nodes
    rms_option_id   VARCHAR(64),           -- Original RMS dropdown option value/id
    parent_option_id VARCHAR(64),          -- Parent's RMS option id (for hierarchy reconstruction)
    label           VARCHAR(512) NOT NULL, -- Exact label as shown in RMS dropdown
    hierarchy_level INTEGER NOT NULL,      -- 1=Category Type, 2=Master Category, 3=Category, 4=Subcategory, 5+=deeper
    full_path       TEXT NOT NULL,         -- e.g. "Academic > Examination > Grade Issue > Re-evaluation"
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    extracted_at    TIMESTAMPTZ,
    verified_at     TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (message_type_id, parent_id, label)
);

CREATE INDEX idx_taxonomy_nodes_parent ON rms_taxonomy.taxonomy_nodes(parent_id);
CREATE INDEX idx_taxonomy_nodes_message_type ON rms_taxonomy.taxonomy_nodes(message_type_id);
CREATE INDEX idx_taxonomy_nodes_full_path ON rms_taxonomy.taxonomy_nodes USING gin(to_tsvector('english', full_path));
```

### Table: `rms_taxonomy.dealing_persons`

```sql
CREATE TABLE rms_taxonomy.dealing_persons (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rms_person_id           VARCHAR(64),            -- Internal RMS id if extractable
    display_name            VARCHAR(255) NOT NULL,  -- Exact name shown in RMS form
    designation             VARCHAR(255),           -- Job title if shown
    department              VARCHAR(255),           -- Department if shown
    official_contact        VARCHAR(255),           -- Only if explicitly shown in authorized UI
    contact_authorized      BOOLEAN NOT NULL DEFAULT FALSE, -- Was contact extracted from authorized UI?
    active                  BOOLEAN NOT NULL DEFAULT TRUE,
    extracted_at            TIMESTAMPTZ,
    verified_at             TIMESTAMPTZ,
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

> **Important**: `official_contact` is populated **only** if visible in the authorized RMS UI. Do not infer or search for contact details outside the RMS form. `contact_authorized = TRUE` flags that the contact was obtained from the authorized source.

### Table: `rms_taxonomy.routing_assignments`

The dealing-person assignment is **not assumed to be at the leaf level**. This table records at which taxonomy node each assignment appears, as observed in the actual RMS form.

```sql
CREATE TABLE rms_taxonomy.routing_assignments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    taxonomy_node_id    UUID NOT NULL REFERENCES rms_taxonomy.taxonomy_nodes(id),
    dealing_person_id   UUID NOT NULL REFERENCES rms_taxonomy.dealing_persons(id),
    assignment_level    INTEGER NOT NULL,  -- The hierarchy_level at which the dealing person was observed
    is_confirmed        BOOLEAN NOT NULL DEFAULT FALSE, -- TRUE = human-verified assignment
    applies_to_subtree  BOOLEAN NOT NULL DEFAULT TRUE,  -- Does assignment propagate to child nodes?
    source_page         VARCHAR(1024),     -- URL where this was observed
    extracted_at        TIMESTAMPTZ,
    verified_at         TIMESTAMPTZ,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (taxonomy_node_id, dealing_person_id)
);
```

---

## Schema: `knowledge`

### Table: `knowledge.documents`

```sql
CREATE TABLE knowledge.documents (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename                VARCHAR(512) NOT NULL,
    drive_file_id           VARCHAR(256),           -- Google Drive file ID
    drive_url               TEXT,                   -- Shareable Drive link
    title                   VARCHAR(512),           -- Extracted or admin-provided; never invented
    category                VARCHAR(128) NOT NULL,  -- circulars | policies | faqs | syllabi | ...
    source_url              TEXT,                   -- Original URL from UMS or upload source
    publication_date        DATE,                   -- From document metadata; NULL if unknown
    valid_from              DATE,                   -- Effective date; NULL if unknown
    valid_until             DATE,                   -- Expiry date; NULL = no expiry
    status                  VARCHAR(32) NOT NULL DEFAULT 'pending_review',
                            -- pending_review | approved | active | expired | superseded | rejected
    supersedes_document_id  UUID REFERENCES knowledge.documents(id), -- NULL unless officially confirmed
    downloaded_at           TIMESTAMPTZ,
    uploaded_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sha256                  VARCHAR(64) NOT NULL UNIQUE,
    content_type            VARCHAR(128) NOT NULL,
    file_size_bytes         BIGINT,
    embedding_model_version VARCHAR(128),           -- Model used to embed this document's chunks
    admin_approved_by       VARCHAR(255),
    admin_approved_at       TIMESTAMPTZ,
    extraction_quality      VARCHAR(32),            -- good | partial | failed | ocr_used
    crawl_run_id            VARCHAR(64),            -- Links to crawler manifest
    verification_notes      TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT valid_status CHECK (
        status IN ('pending_review', 'approved', 'active', 'expired', 'superseded', 'rejected')
    )
);

CREATE INDEX idx_documents_status ON knowledge.documents(status);
CREATE INDEX idx_documents_valid_until ON knowledge.documents(valid_until);
CREATE INDEX idx_documents_sha256 ON knowledge.documents(sha256);
CREATE INDEX idx_documents_category ON knowledge.documents(category);
```

### Table: `knowledge.chunks`

```sql
CREATE TABLE knowledge.chunks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES knowledge.documents(id) ON DELETE CASCADE,
    chunk_index         INTEGER NOT NULL,
    chunk_text          TEXT NOT NULL,
    token_count         INTEGER NOT NULL,
    qdrant_point_id     UUID,                   -- Qdrant vector point ID
    embedding_model     VARCHAR(128) NOT NULL,
    embedded_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX idx_chunks_document_id ON knowledge.chunks(document_id);
```

---

## Schema: `faculty`

### Table: `faculty.directory`

```sql
CREATE TABLE faculty.directory (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    faculty_name        VARCHAR(255) NOT NULL,
    designation         VARCHAR(255),
    department          VARCHAR(255),
    school              VARCHAR(255),
    building_block      VARCHAR(64),            -- e.g., "Block 34"
    floor               VARCHAR(32),
    cabin_number        VARCHAR(32),
    consultation_days   TEXT[],                 -- e.g., ARRAY['Mon', 'Wed', 'Fri']
    consultation_start  TIME,
    consultation_end    TIME,
    email               VARCHAR(255),
    employee_id         VARCHAR(64) UNIQUE,
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    last_verified       DATE,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_faculty_name_trgm ON faculty.directory 
    USING gin(faculty_name gin_trgm_ops);    -- Requires pg_trgm extension for fuzzy search
CREATE INDEX idx_faculty_department ON faculty.directory(department);
```

---

## Schema: `analytics`

### Table: `analytics.query_logs`

```sql
CREATE TABLE analytics.query_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID,                   -- Browser session (no personal identity stored)
    raw_query           TEXT NOT NULL,
    normalized_query    TEXT,
    intent_tier         VARCHAR(32),            -- informational | directory | transactional
    resolution          VARCHAR(32),            -- deflected | directory_served | escalated | fallback
    retrieval_score     FLOAT,
    threshold_met       BOOLEAN,
    response_latency_ms INTEGER,
    query_embedding     VECTOR(384),            -- Stored for nightly clustering (pgvector extension)
    included_in_cluster BOOLEAN NOT NULL DEFAULT FALSE,
    cluster_id          UUID REFERENCES analytics.cluster_results(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_query_logs_resolution ON analytics.query_logs(resolution);
CREATE INDEX idx_query_logs_created_at ON analytics.query_logs(created_at);
CREATE INDEX idx_query_logs_cluster ON analytics.query_logs(cluster_id);
```

### Table: `analytics.cluster_results`

```sql
CREATE TABLE analytics.cluster_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_date            DATE NOT NULL,
    cluster_label       INTEGER NOT NULL,       -- DBSCAN label (-1 = noise)
    cluster_size        INTEGER NOT NULL,
    top_keywords        TEXT[],                 -- TF-IDF extracted terms
    representative_queries TEXT[],             -- Sample queries nearest to centroid
    canonical_answer    TEXT,                  -- Admin-published answer (NULL until set)
    canonical_published_at TIMESTAMPTZ,
    canonical_published_by VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Table: `analytics.top_trends`

```sql
CREATE TABLE analytics.top_trends (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trend_date          DATE NOT NULL,
    rank                INTEGER NOT NULL CHECK (rank BETWEEN 1 AND 5),
    cluster_id          UUID REFERENCES analytics.cluster_results(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (trend_date, rank)
);
```

---

## Schema: `auth`

### Table: `auth.admin_users`

```sql
CREATE TABLE auth.admin_users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username            VARCHAR(128) NOT NULL UNIQUE,
    email               VARCHAR(255) NOT NULL UNIQUE,
    password_hash       VARCHAR(256) NOT NULL,  -- bcrypt
    role                VARCHAR(32) NOT NULL DEFAULT 'reviewer',
                        -- reviewer | approver | superadmin
    department          VARCHAR(255),
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    last_login          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Required PostgreSQL Extensions

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";     -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";       -- Fuzzy name matching for faculty lookup
CREATE EXTENSION IF NOT EXISTS "vector";        -- pgvector for query_logs embeddings (optional)
CREATE EXTENSION IF NOT EXISTS "unaccent";      -- Handle accented characters in names
```

---

## Key Constraints and Rules

| Rule | Enforcement |
|---|---|
| Only `status = active` documents are queried by RAG | Application-level filter AND Qdrant payload filter |
| `sha256` must be unique — no duplicate file ingestion | PostgreSQL UNIQUE constraint |
| Dealing person NOT assumed to be at leaf level | `routing_assignments.assignment_level` captures actual level |
| `official_contact` populated only from authorized UI | `contact_authorized` flag must be TRUE |
| `supersedes_document_id` only when officially confirmed | Application enforces; not auto-detected |
| Dates never invented — NULL when unknown | All date columns nullable; NULL ≠ "no date" |
