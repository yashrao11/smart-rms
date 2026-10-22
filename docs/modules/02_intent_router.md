# Module 2 — Dual-Tier Intent & Entity Routing Engine

> **Input**: `ProcessedQuery` from Module 1
> **Output**: Routing decision with target subsystem and (for transactional queries) RMS category path
> **Location**: `src/intent_router/`

---

## Purpose

Classify every incoming query into one of three tiers and route it to the correct subsystem. This module determines **what kind of answer is needed** before any retrieval or lookup begins.

Getting the routing right is more important than getting a fast answer — an incorrect escalation to RAG for a transactional query, or a false deflection for a personal dispute, is a system failure.

---

## Three Routing Tiers

### Tier 1: Informational (→ RAG Engine)

Factual, policy-level, or institutional questions that can be answered from a verified document.

**Signals**:
- No personal account identifiers mentioned
- Question is about dates, deadlines, schedules, policies, procedures
- Could apply to any student (not "my" something)

**Examples**:
- "When does the 7th semester MTE begin?"
- "What is the fee submission deadline?"
- "What is the attendance policy for lab courses?"

### Tier 2: Directory (→ Faculty Lookup SQL)

Questions about a specific faculty member's location, office, or schedule.

**Signals**:
- `faculty_name` entity extracted by Module 1
- Question involves: cabin, office, floor, block, consultation hours, "where to find"

**Examples**:
- "Where is Dr. Sharma's office?"
- "When can I meet Prof. Gupta?"
- "Which block is Dr. Mehta in?"

### Tier 3: Transactional (→ RMS Ticket Pre-fill)

Personal, account-specific disputes requiring authorized human decision.

**Signals**:
- Mentions: "my grade", "my fee", "my attendance", "my registration", "my scholarship"
- Dispute keywords: "wrong", "incorrect", "not updated", "dispute", "refund", "correction"
- Ambiguous queries where a wrong answer could harm the student

**Examples**:
- "My attendance is showing 68% but I attended all classes"
- "I was charged extra fee in my account"
- "My internal marks are incorrect in the portal"

---

## Routing Logic (Rule-Based First)

```python
def route(query: ProcessedQuery) -> RoutingDecision:
    
    # Step 1: Directory signals (highest priority when faculty name found)
    if query.entities.faculty_names and is_location_query(query.normalized_text):
        return RoutingDecision(tier="directory", target="faculty_lookup")
    
    # Step 2: Transactional signals
    if has_transactional_signals(query.normalized_text, query.entities):
        rms_path = suggest_rms_path(query)   # From rms_taxonomy table
        return RoutingDecision(
            tier="transactional",
            target="rms_ticket",
            rms_category_path=rms_path
        )
    
    # Step 3: Default — informational
    return RoutingDecision(tier="informational", target="rag")
```

**Tie-break rule**: When the router cannot distinguish informational from transactional, default to **transactional**. It is safer to route a factual question to a human than to risk giving a wrong answer to a personal dispute.

---

## Transactional Signal Detection (`transactional_signals.py`)

```python
TRANSACTIONAL_KEYWORDS = [
    "my grade", "my marks", "my fee", "my attendance", "my registration",
    "my account", "my scholarship", "my result", "my certificate",
    "wrong", "incorrect", "error", "not updated", "not reflecting",
    "dispute", "refund", "correction", "complaint", "issue with my",
    "overcharged", "deducted", "discrepancy"
]

FIRST_PERSON_POSSESSIVES = ["my ", "mine", "i was", "i have been", "my record"]
```

A query is transactional if:
- It contains a first-person possessive AND a complaint/dispute keyword, OR
- It explicitly mentions a personal record type (grade, fee, attendance) with any negative sentiment signal

---

## RMS Path Suggestion (`rms_path_suggester.py`)

When a query is classified as transactional, pre-fill the ticket with the best-matching RMS category path:

```python
def suggest_rms_path(query: ProcessedQuery) -> RMSCategoryPath | None:
    """
    1. Build a search string from the query's key terms
    2. Full-text search against rms_taxonomy.taxonomy_nodes.full_path
    3. Return the best-matching path and its dealing person
    4. If no confident match → return None (student fills form manually)
    """
    results = db.execute("""
        SELECT tn.full_path, tn.id, dp.display_name, dp.designation
        FROM rms_taxonomy.taxonomy_nodes tn
        JOIN rms_taxonomy.routing_assignments ra ON ra.taxonomy_node_id = tn.id
        JOIN rms_taxonomy.dealing_persons dp ON ra.dealing_person_id = dp.id
        WHERE tn.active = TRUE AND ra.is_confirmed = TRUE
          AND to_tsvector('english', tn.full_path) @@ plainto_tsquery('english', :search_terms)
        ORDER BY ts_rank(to_tsvector('english', tn.full_path), 
                         plainto_tsquery('english', :search_terms)) DESC
        LIMIT 1
    """, {"search_terms": build_search_terms(query)})
    
    if results and results[0]["rank"] > MINIMUM_TAXONOMY_MATCH_SCORE:
        return RMSCategoryPath(**results[0])
    return None
```

**Critical**: Only return an RMS path that was extracted from the actual RMS form (`is_confirmed = TRUE`). Never suggest a made-up path.

---

## Output Contract

```python
@dataclass
class RoutingDecision:
    tier: Literal["informational", "directory", "transactional"]
    target: Literal["rag", "faculty_lookup", "rms_ticket"]
    confidence: float           # Router's own confidence (0.0–1.0)
    rms_category_path: RMSCategoryPath | None  # Populated only for transactional
    routing_latency_ms: int

@dataclass
class RMSCategoryPath:
    message_type: str
    category_type: str | None
    master_category: str | None
    category: str | None
    subcategory: str | None
    full_path: str
    dealing_person_name: str
    dealing_person_designation: str | None
    taxonomy_node_id: str       # UUID for audit
```

---

## Tests (`tests/unit/test_intent_router.py`)

| Test | Input | Expected tier |
|---|---|---|
| `test_faculty_location_query` | "Where is Dr. Sharma?" | directory |
| `test_fee_deadline_info` | "When is fee deadline?" | informational |
| `test_personal_fee_dispute` | "My fee was deducted twice" | transactional |
| `test_attendance_correction` | "My attendance is wrong" | transactional |
| `test_ambiguous_defaults_transactional` | "I have a problem with attendance" | transactional |
| `test_policy_query` | "What is the re-appear exam policy?" | informational |
| `test_exam_schedule` | "When does ETE start for 7th sem?" | informational |
| `test_rms_path_populated` | transactional query with fee keywords | rms_category_path not None |
