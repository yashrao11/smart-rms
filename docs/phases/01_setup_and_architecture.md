# Phase 01 — Requirements, Architecture & Project Setup

> **Goal**: Establish the finalized scope, schemas, and development environment before writing any feature code.
> **Deliverable**: Architecture design, repository structure, task assignments, working dev environment.

---

## Prerequisites Checklist

- [ ] LPU IT/administration authorization for UMS document collection obtained
- [ ] Google Drive API credentials created (scoped to target folder)
- [ ] All team members have cloned the repository
- [ ] `.gitignore` confirmed to exclude `.playwright_session/`, `.secrets/`, `*.env`
- [ ] Project supervisor has confirmed scope (including attendance analytics status)
- [ ] Vector DB choice confirmed: **Qdrant**
- [ ] Relational DB choice confirmed: **PostgreSQL**

---

## Tasks

### 1.1 Finalize MVP Scope

Define exactly what will be demonstrated at the capstone evaluation. Distinguish:

| Feature | MVP (must have) | Post-MVP (if time permits) |
|---|---|---|
| Query pre-processing and normalization | ✅ | |
| Dual-tier intent routing | ✅ | |
| RAG engine with confidence guardrail | ✅ | |
| Faculty directory lookup | ✅ | |
| TTL-based document expiry | ✅ | |
| Admin document upload portal | ✅ | |
| DBSCAN clustering + top-5 dashboard | ✅ | |
| RMS taxonomy parity routing | ✅ | |
| UMS document crawler | | ✅ |
| RMS taxonomy extractor | | ✅ |
| Attendance analytics | | ✅ |
| Full Docker deployment | ✅ | |

### 1.2 Team Role Assignments

Assign each module to a team member. Suggested split for 6-person team:

| Member | Primary module | Supporting module |
|---|---|---|
| Member 1 | Module 1 (Preprocessing) + Module 2 (Router) | API integration |
| Member 2 | Module 3 (RAG Engine) | Qdrant setup |
| Member 3 | Module 4 (Faculty Lookup) + PostgreSQL schema | Faculty data collection |
| Member 4 | Module 5 (TTL Manager) + Admin portal backend | Document ingestion |
| Member 5 | Module 6 (Clustering) + Analytics | Admin dashboard frontend |
| Member 6 | Frontend (React.js) + API integration | Testing |

### 1.3 Repository Structure

Create the complete directory structure (empty placeholder files where needed):

```
smart-rms/
├── .gitignore                    ✅ Done
├── .env.example                  ← Create this
├── README.md                     ✅ Exists
├── SMART-RMS_Problem_Statement_new.docx
├── docker-compose.yml            ← Create in Phase 1
├── requirements.txt              ← Create in Phase 1
├── docs/                         ✅ Being built
├── config/
│   ├── rag_config.yaml
│   ├── clustering_config.yaml
│   └── crawler_config.yaml
├── src/
│   ├── __init__.py
│   ├── main.py                   ← FastAPI app entry point
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   └── migrations/           ← Alembic migration files
│   ├── preprocessing/
│   ├── intent_router/
│   ├── retrieval/
│   ├── faculty_lookup/
│   ├── ttl_manager/
│   ├── clustering/
│   └── crawler/
├── frontend/                     ← React.js app
├── tests/
│   ├── unit/
│   ├── integration/
│   └── crawler/
├── scripts/
│   ├── rms_extract_discover.py
│   ├── import_rms_taxonomy.py
│   └── seed_faculty_directory.py
└── data/
    ├── metadata/
    │   └── document_index.csv    ← Header row only to start
    ├── faculty/
    │   └── faculty_directory.csv ← Seed data
    └── crawler/
        ├── manifests/
        ├── discovery_reports/
        └── logs/
```

### 1.4 Environment Variables (`.env.example`)

```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=smart_rms
POSTGRES_USER=smart_rms_user
POSTGRES_PASSWORD=your_password_here

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Google Drive
GDRIVE_CREDENTIALS_PATH=.secrets/gdrive_service_account.json
GDRIVE_TARGET_FOLDER_ID=1o31DA1NLrK1vTFcgUMZ0Qb1y_FXBXM71

# JWT
JWT_SECRET_KEY=generate-a-random-32-char-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# RAG
RAG_CONFIDENCE_THRESHOLD=0.82
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# LLM (optional — local Ollama)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2:3b
LLM_BASE_URL=http://localhost:11434
```

### 1.5 Git Branching Strategy

```
main              ← Protected; only merge via PR
  └── develop     ← Integration branch; all features merged here first
        ├── feature/preprocessing
        ├── feature/intent-router
        ├── feature/rag-engine
        ├── feature/faculty-lookup
        ├── feature/ttl-manager
        ├── feature/clustering
        ├── feature/frontend
        └── feature/rms-taxonomy-extractor
```

### 1.6 Database Initialization

Run Alembic migrations to create all schemas and tables:

```bash
# Initialize Alembic
alembic init src/db/migrations

# Edit alembic.ini to point to PostgreSQL
# Create migration: alembic revision --autogenerate -m "initial schema"

# Apply:
alembic upgrade head
```

### 1.7 Qdrant Collection Setup

Create all eight Qdrant collections via a one-time setup script:

```bash
python scripts/setup_qdrant_collections.py
```

---

## Definition of Done for Phase 1

- [ ] All directories exist in the repository
- [ ] `requirements.txt` lists all agreed dependencies with pinned versions
- [ ] `.env.example` committed (no real values)
- [ ] `docker-compose.yml` starts PostgreSQL + Qdrant successfully
- [ ] Alembic migrations create all tables without errors
- [ ] Qdrant collections exist (verified via Qdrant dashboard at `:6333/dashboard`)
- [ ] All team members can `git pull` and run `docker compose up` without errors
- [ ] Phase 1 documentation reviewed and approved by team lead
