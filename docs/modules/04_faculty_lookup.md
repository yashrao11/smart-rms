# Module 4 — Faculty Directory & Cabin Lookup

> **Input**: `ProcessedQuery` with `faculty_name` entity (directory tier)
> **Output**: Faculty card with exact location and consultation schedule
> **Location**: `src/faculty_lookup/`

---

## Responsibility

Answer "where is [faculty member]?" and "when can I meet [faculty member]?" queries with **deterministic, verified data** from a relational database. No LLM is involved — this is a direct SQL lookup.

---

## Why No LLM for This?

Faculty cabin numbers, building blocks, and consultation hours are precise facts. An LLM that approximates or guesses cabin numbers creates real-world harm (students walk to the wrong building). A SQL lookup returns exact, human-verified data or returns nothing.

---

## Database Source

Table: `faculty.directory` (see `docs/database/01_postgresql_schema.md`)

Initial data populated from: `data/faculty/faculty_directory.csv` (manually verified by the team from official sources — department noticeboards, official LPU website, faculty profiles).

---

## Lookup Logic

```python
async def lookup_faculty(
    faculty_name: str,
    department: str | None = None
) -> list[FacultyCard]:
    """
    1. Fuzzy name match using pg_trgm (handles "Sharma" matching "Dr. Rajesh Sharma")
    2. Optional department filter if entity was extracted
    3. Return all matches (may be multiple people with similar names)
    4. If zero matches → return empty list (do not guess)
    """
    
    query = """
        SELECT
            faculty_name, designation, department, school,
            building_block, floor, cabin_number,
            consultation_days, consultation_start, consultation_end,
            last_verified
        FROM faculty.directory
        WHERE active = TRUE
          AND faculty_name % :name_query   -- pg_trgm similarity
        """
    
    if department:
        query += " AND department ILIKE :department"
    
    query += " ORDER BY similarity(faculty_name, :name_query) DESC LIMIT 5"
```

---

## Output Contract

```python
@dataclass
class FacultyCard:
    faculty_name: str
    designation: str | None
    department: str | None
    building_block: str | None      # e.g., "Block 34"
    floor: str | None               # e.g., "4th Floor"
    cabin_number: str | None        # e.g., "Cabin 408"
    consultation_days: list[str]    # e.g., ["Mon", "Wed", "Fri"]
    consultation_start: time | None
    consultation_end: time | None
    last_verified: date | None      # When this record was last checked

@dataclass
class DirectoryResult:
    matches: list[FacultyCard]
    match_count: int
    lookup_latency_ms: int
    warning: str | None             # e.g., "Multiple faculty found with similar names"
```

---

## Data Maintenance

The faculty directory must be kept current. Stale cabin assignments cause student frustration.

| Action | Frequency | Owner |
|---|---|---|
| Full directory verification | Each semester start | Admin / Team member 3 |
| Individual record update | When faculty notifies change | Admin via portal |
| New faculty addition | On joining | Admin |
| Mark inactive | On departure | Admin |

The admin portal includes a faculty directory management view (Phase 6).

---

## CSV Format (`data/faculty/faculty_directory.csv`)

```csv
faculty_name,designation,department,school,building_block,floor,cabin_number,consultation_days,consultation_start,consultation_end,email,employee_id,active,last_verified,notes
"Dr. Example Name","Assistant Professor","Computer Science & Engineering","Lovely School of Technology","Block 34","4th Floor","Cabin 408","Mon|Wed|Fri","14:00","16:00","example@lpu.co.in","LPU12345",TRUE,2026-10-01,""
```

`consultation_days` uses pipe-delimited values in CSV (converted to array on import).

---

## Tests (`tests/unit/test_faculty_lookup.py`)

| Test | Input | Expected |
|---|---|---|
| `test_exact_name_match` | "Dr. Sharma" (exists in DB) | Returns FacultyCard with location |
| `test_fuzzy_name_match` | "sharma" (lowercase, no title) | Still returns match via pg_trgm |
| `test_no_match` | "Dr. Nonexistent" | Returns empty list, no error |
| `test_multiple_matches_warning` | Common surname | Returns all matches + warning |
| `test_department_filter` | Name + department | Narrows results |
| `test_inactive_excluded` | Faculty marked inactive=FALSE | Not returned |
