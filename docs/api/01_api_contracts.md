# FastAPI Contract Specifications — SMART-RMS

> **Backend**: Python + FastAPI
> **Base URL**: `/api/v1`
> **Auth**: JWT Bearer token for admin endpoints; no auth for student query endpoint

---

## Endpoints Overview

| Method | Path | Tier | Purpose |
|---|---|---|---|
| POST | `/query/resolve` | Public | Submit a student query for resolution |
| GET | `/query/suggestions` | Public | Autocomplete query suggestions |
| GET | `/faculty/lookup` | Public | Look up faculty cabin and office hours |
| POST | `/tickets/create` | Public | Submit a ticket (pre-filled from routing) |
| GET | `/tickets/{id}/status` | Public | Check ticket status |
| GET | `/admin/documents/review-queue` | Admin | List pending documents |
| POST | `/admin/documents/{id}/approve` | Admin | Approve a document for RAG indexing |
| POST | `/admin/documents/{id}/reject` | Admin | Reject a document |
| POST | `/admin/documents/upload` | Admin | Manual document upload |
| GET | `/admin/trends/today` | Admin | Today's top-5 cluster trends |
| POST | `/admin/trends/{cluster_id}/publish-answer` | Admin | Publish canonical answer |
| GET | `/admin/taxonomy/paths` | Admin | Browse full RMS taxonomy |
| GET | `/health` | Public | Health check |

---

## 1. `POST /api/v1/query/resolve`

**Purpose**: Main query resolution endpoint. Returns either an answer card, faculty card, or a ticket routing suggestion.

### Request

```json
{
  "query": "When does the mid-term examination for 7th semester begin?",
  "session_id": "optional-uuid-for-clustering"
}
```

### Response — Answer Card (deflected)

```json
{
  "outcome": "deflected",
  "answer": {
    "text": "Mid-term examinations for 7th semester begin on 10 November 2026...",
    "retrieval_score": 0.91,
    "threshold_met": true,
    "sources": [
      {
        "document_title": "Academic Calendar — 7th Semester 2026-27",
        "excerpt": "MTE commencement: 10 November 2026...",
        "source_url": "https://lpu.in/.../academic_calendar.pdf",
        "drive_url": "https://drive.google.com/...",
        "valid_from": "2026-08-01",
        "valid_until": "2027-05-31"
      }
    ]
  },
  "response_latency_ms": 340
}
```

### Response — Faculty Card (directory)

```json
{
  "outcome": "directory",
  "faculty": {
    "name": "Dr. Example Name",
    "department": "Computer Science & Engineering",
    "building_block": "Block 34",
    "floor": "4th Floor",
    "cabin_number": "Cabin 408",
    "consultation_days": ["Mon", "Wed", "Fri"],
    "consultation_start": "14:00",
    "consultation_end": "16:00"
  },
  "response_latency_ms": 55
}
```

### Response — Escalation (fallback or transactional)

```json
{
  "outcome": "escalate",
  "reason": "low_confidence",
  "retrieval_score": 0.64,
  "suggested_ticket": {
    "message_type": "Fee Related",
    "category_type": "Fee Refund",
    "master_category": "Billing Dispute",
    "category": "Incorrect Fee Charged",
    "subcategory": null,
    "full_path": "Fee Related | Fee Refund | Billing Dispute | Incorrect Fee Charged",
    "dealing_person": {
      "name": "Example Dealing Person",
      "designation": "Accounts Officer"
    }
  },
  "response_latency_ms": 180
}
```

---

## 2. `GET /api/v1/faculty/lookup`

**Query params**: `name` (required), `department` (optional)

### Response

```json
{
  "results": [
    {
      "id": "uuid",
      "faculty_name": "Dr. Example",
      "department": "CSE",
      "building_block": "Block 34",
      "floor": "4th",
      "cabin_number": "408",
      "consultation_days": ["Mon", "Wed"],
      "consultation_start": "14:00",
      "consultation_end": "16:00"
    }
  ],
  "count": 1
}
```

---

## 3. `POST /api/v1/admin/documents/{id}/approve`

**Auth**: Bearer JWT (admin role: `approver` or `superadmin`)

### Request body

```json
{
  "title": "Mid-Term Examination Schedule — Nov 2026",
  "category": "exam_schedule",
  "valid_from": "2026-11-01",
  "valid_until": "2026-11-30",
  "supersedes_document_id": null,
  "verification_notes": "Verified against official LPU notice board circular ref #1234"
}
```

### Response

```json
{
  "document_id": "uuid",
  "status": "approved",
  "approved_by": "admin_username",
  "approved_at": "2026-10-22T19:30:00Z",
  "next_step": "extraction_queued"
}
```

---

## 4. `GET /api/v1/admin/trends/today`

### Response

```json
{
  "date": "2026-10-22",
  "top_trends": [
    {
      "rank": 1,
      "cluster_id": "uuid",
      "top_keywords": ["fee", "deadline", "payment", "portal"],
      "representative_queries": [
        "What is the last date to pay semester fee?",
        "Fee submission deadline 7th sem?"
      ],
      "cluster_size": 47,
      "canonical_answer": null,
      "canonical_published_at": null
    }
  ]
}
```

---

## 5. Error Responses (Standard Format)

```json
{
  "error": {
    "code": "QUERY_TOO_LONG",
    "message": "Query exceeds maximum length of 2000 characters",
    "field": "query"
  }
}
```

| HTTP Code | When used |
|---|---|
| 400 | Validation error |
| 401 | Missing or invalid JWT |
| 403 | Insufficient role |
| 404 | Resource not found |
| 422 | Pydantic validation failure |
| 429 | Rate limit exceeded |
| 500 | Internal error (never expose stack traces) |

---

## 6. Rate Limiting

| Endpoint | Limit |
|---|---|
| `POST /query/resolve` | 30 requests/minute per IP |
| All admin endpoints | 60 requests/minute per token |

---

## 7. Authentication Flow (Admin Only)

```
POST /api/v1/auth/login
  Body: { "username": "...", "password": "..." }
  Response: { "access_token": "jwt...", "expires_in": 3600 }

All admin requests:
  Header: Authorization: Bearer <access_token>
```

Student-facing endpoints are **unauthenticated** — no student login required.
