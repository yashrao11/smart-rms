# RMS Taxonomy — PostgreSQL Table Design

> **Context**: Companion to `docs/crawler/02_rms_taxonomy_extractor.md`
> This document explains the design decisions behind the `rms_taxonomy` schema.

---

## Why a Dedicated Schema?

The LPU RMS category hierarchy is the **authoritative routing structure** for all student grievances and queries. SMART-RMS must replicate it exactly — not approximate it, not invent parallel categories.

The `rms_taxonomy` schema:
- Is **read-only** from the perspective of SMART-RMS's query-resolution logic
- Is **populated** by the RMS Taxonomy Extractor or a human-provided admin export
- Is **not modified** by any student-facing action
- Is **human-reviewed** before any routing rules are activated

---

## Entity Relationship Diagram

```
rms_taxonomy.message_types
    │ (1)
    │ has many
    ▼ (*)
rms_taxonomy.taxonomy_nodes ──── self-referencing (parent_id)
    │ (*)
    │ assigned via
    ▼ (*)
rms_taxonomy.routing_assignments
    │ (*)
    │ references
    ▼ (1)
rms_taxonomy.dealing_persons
```

---

## Key Design Decisions

### 1. Self-Referencing `taxonomy_nodes` Table

Rather than separate tables for Category Type, Master Category, Category, and Subcategory, a single self-referencing table is used.

**Why**: The actual RMS form may have 4 levels in some branches and 5+ in others. A fixed-column design (one column per level) would break when deeper levels appear. The self-referencing design handles arbitrary depth.

**Trade-off**: Querying the full path requires a recursive CTE, which is slightly more complex but is a standard PostgreSQL pattern.

### Full-path reconstruction query:

```sql
WITH RECURSIVE path AS (
    -- Start at a leaf node
    SELECT id, label, parent_id, hierarchy_level, 1 as depth,
           CAST(label AS TEXT) as path_str
    FROM rms_taxonomy.taxonomy_nodes
    WHERE id = :leaf_node_id

    UNION ALL

    -- Walk up to root
    SELECT t.id, t.label, t.parent_id, t.hierarchy_level, p.depth + 1,
           t.label || ' > ' || p.path_str
    FROM rms_taxonomy.taxonomy_nodes t
    JOIN path p ON t.id = p.parent_id
)
SELECT path_str FROM path WHERE parent_id IS NULL;
```

### 2. `routing_assignments.assignment_level`

The dealing person is **not assumed to be assigned at the leaf node**. The LPU RMS form may auto-populate the dealing person field when:
- A Message Type is selected (level 1)
- A Master Category is selected (level 3)
- A Category is selected (level 4)
- Or any other level

`assignment_level` records the `hierarchy_level` at which the dealing person was observed. `applies_to_subtree = TRUE` means all child nodes of that taxonomy node also use the same dealing person unless overridden by a lower-level assignment.

### 3. `dealing_persons.contact_authorized`

Contact information (email, phone) for a dealing person is populated **only if it appeared in the authorized RMS UI** that the account owner was accessing.

Do not:
- Search the internet for faculty email addresses
- Infer contact from the faculty directory table
- Copy contact from unofficial sources

The flag `contact_authorized = TRUE` in the database means: "this contact was read from the authorized RMS form or an admin-provided export."

### 4. `notes` Field on Every Table

Every table includes a `notes TEXT` column. This is the designated place for:
- Extraction ambiguities ("Dealing person changed between two extractions")
- Human review comments ("Confirmed by Dr. X on 2026-10-25")
- Known issues ("This node's dropdown failed to load in 3/5 attempts")

Do not delete or overwrite notes — append with timestamps.

---

## Routing Query Used by SMART-RMS

When the intent router classifies a query as `transactional`, SMART-RMS must pre-populate the ticket form with the correct category path and dealing person. The query:

```sql
-- Find the best-matching taxonomy path for a transactional query
-- (simplified; actual implementation uses intent router's extracted entities)

SELECT
    mt.label AS message_type,
    tn.full_path,
    tn.hierarchy_level,
    dp.display_name AS dealing_person,
    dp.designation,
    ra.assignment_level,
    ra.applies_to_subtree
FROM rms_taxonomy.taxonomy_nodes tn
JOIN rms_taxonomy.message_types mt ON tn.message_type_id = mt.id
JOIN rms_taxonomy.routing_assignments ra ON ra.taxonomy_node_id = tn.id
JOIN rms_taxonomy.dealing_persons dp ON ra.dealing_person_id = dp.id
WHERE tn.active = TRUE
  AND mt.active = TRUE
  AND dp.active = TRUE
  AND ra.is_confirmed = TRUE
ORDER BY tn.full_path;
```

The intent router uses keyword matching against `full_path` and `label` fields to find the closest taxonomy path for the student's described problem, then presents the pre-filled form for student confirmation before submission.

---

## Import Validation Rules

Before any row is imported from `rms_taxonomy_inventory.csv` to PostgreSQL, the importer checks:

| Check | Rule |
|---|---|
| `message_type` not null | Every row must have a message type |
| `full_path` not null | Every row must have a full path string |
| `hierarchy_level` consistent | Level must match the depth of `full_path` segments |
| `dealing_person_name` null consistency | If NULL, `dealing_person_id` must also be NULL |
| `notes` for NULL paths | Rows with NULL category/subcategory must explain why in `notes` |
| No invented dates | `verified_at` must be a real extraction timestamp |
| `active_status` boolean | Must be TRUE or FALSE, not a string |

Rows failing validation are logged to `data/crawler/logs/taxonomy_import_errors.csv` for human review. They are not imported until corrected.
