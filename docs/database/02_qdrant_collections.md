# Qdrant Vector Collections — SMART-RMS

> **Qdrant version**: Latest stable (self-hosted via Docker)
> **Embedding dimension**: 384 (BAAI/bge-small-en-v1.5)

---

## Collection Design Principles

1. **One collection per document category** — Allows targeted retrieval against specific document types without cross-category noise.
2. **TTL and approval enforced via payload filters** — Every query includes `status = active` AND `valid_until > today` as mandatory filters.
3. **Payload carries all metadata needed for an answer card** — No second database round-trip needed to display a citation.
4. **Points are deleted (not soft-deleted) on expiry** — The nightly sweep removes expired points from Qdrant; the authoritative record of the document remains in PostgreSQL.

---

## Collections

### `knowledge_circulars`

Official university circulars and administrative notices.

```python
from qdrant_client.models import Distance, VectorParams

client.create_collection(
    collection_name="knowledge_circulars",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)
```

**Point payload schema**:

```json
{
  "document_id": "uuid",
  "chunk_id": "uuid",
  "chunk_index": 0,
  "chunk_text": "string (≤512 tokens)",
  "document_title": "string",
  "category": "circulars",
  "source_url": "string",
  "drive_url": "string",
  "valid_from": "2026-01-01",
  "valid_until": "2026-12-31",
  "status": "active",
  "approved": true,
  "embedding_model": "BAAI/bge-small-en-v1.5",
  "embedded_at": "2026-10-22T00:00:00Z"
}
```

---

### `knowledge_policies`

University policies, student codes of conduct, ordinances, and standing orders.

Same vector config as `knowledge_circulars`. Payload identical; `category = "policies"`.

---

### `knowledge_faqs`

Frequently Asked Questions published by university departments.

Same vector config. `category = "faqs"`.

---

### `knowledge_academic_calendar`

Academic calendars, term schedules, holiday lists, exam timetables.

Same vector config. `category = "academic_calendar"`.

---

### `knowledge_syllabi`

Course syllabi, program guides, credit requirements.

Same vector config. `category = "syllabi"`.

---

### `knowledge_placement`

Placement notices, company visit schedules, eligibility criteria.

Same vector config. `category = "placement"`.

---

### `knowledge_hostel`

Hostel rules, guidelines, fee schedules, warden notices.

Same vector config. `category = "hostel"`.

---

### `knowledge_general`

Documents that do not fit specific categories above. Used as a catch-all; admin categorizes new documents more specifically over time.

Same vector config. `category = "general"`.

---

## Mandatory Query Filter (Applied to Every Search)

Every RAG retrieval call must include this filter — no exceptions:

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
from datetime import date

today = date.today().isoformat()

mandatory_filter = Filter(
    must=[
        FieldCondition(key="status", match=MatchValue(value="active")),
        FieldCondition(key="approved", match=MatchValue(value=True)),
        # Exclude documents where valid_until has passed (NULL means no expiry → always included)
        # Documents with valid_until < today are removed by the nightly sweep,
        # but this filter is a safety net.
    ]
)
```

> **Note on NULL `valid_until`**: Documents with no expiry date have `valid_until = null` in PostgreSQL. In Qdrant, store as `valid_until = "9999-12-31"` to simplify range filtering.

---

## Search Function Signature

```python
async def retrieve_chunks(
    query_vector: list[float],
    collection_names: list[str],       # Which collections to search
    top_k: int = 5,
    score_threshold: float = 0.82,     # Configurable; from rag_config.yaml
    category_filter: str | None = None # Optional: restrict to a specific category
) -> list[ScoredPoint]:
    ...
```

The function queries all specified collections, merges results, re-ranks by score, and returns the top K above the threshold.

---

## Index and Performance Notes

- **HNSW index**: Qdrant uses HNSW by default. Default `m=16, ef_construct=100` is sufficient for the expected corpus size (< 100K chunks for a university knowledge base).
- **Re-indexing on model change**: If the embedding model version changes, all collections must be re-embedded and re-indexed. The `embedding_model` payload field tracks which model was used per chunk.
- **Payload index**: Create payload indices for frequently filtered fields:

```python
client.create_payload_index("knowledge_circulars", "status", "keyword")
client.create_payload_index("knowledge_circulars", "approved", "bool")
client.create_payload_index("knowledge_circulars", "valid_until", "keyword")
```
