# Module 1 — Data Ingestion & Query Pre-Processing

> **Input**: Raw student query string (up to 2000 characters)
> **Output**: Structured query object with normalized text, extracted entities, timestamp
> **Location**: `src/preprocessing/`

---

## Responsibility

This module is the **first touchpoint** for every student query. It prepares a clean, standardized representation that all downstream modules can rely on without handling raw text.

It does **not** classify intent — that is Module 2's job. It only normalizes and extracts facts.

---

## Sub-Components

### 1.1 Text Normalizer (`normalizer.py`)

```python
def normalize(raw_query: str) -> str:
    """
    1. Strip leading/trailing whitespace
    2. Collapse multiple spaces to single space
    3. Remove HTML tags if accidentally pasted
    4. Normalize Unicode (NFC form)
    5. Convert to lowercase for processing (preserve original for display)
    6. Remove control characters
    7. Truncate at 2000 characters
    """
```

### 1.2 Acronym Expander (`acronym_expander.py`)

Lookup table approach — stored in `config/acronyms.yaml` (extensible by admin).

**Initial acronym table** (expand as real queries reveal more):

| Acronym | Expansion |
|---|---|
| `MTE` | Mid-Term Examination |
| `ETE` | End-Term Examination |
| `CA` | Continuous Assessment |
| `RP` | Re-appear Exam |
| `UMS` | University Management System |
| `LPU` | Lovely Professional University |
| `CSE` | Computer Science & Engineering |
| `ECE` | Electronics & Communication Engineering |
| `RMS` | Relationship Management System |
| `HOD` | Head of Department |
| `DSW` | Dean of Student Welfare |
| `COE` | Controller of Examinations |
| `DRC` | Department Result Committee |
| `GPA` | Grade Point Average |
| `SGPA` | Semester Grade Point Average |
| `CGPA` | Cumulative Grade Point Average |
| `OD` | On-Duty Leave |
| `MCQ` | Multiple Choice Question |

**Expansion rules**:
- Match whole-word only (do not expand "CAT" to "Continuous Assessment T")
- Case-insensitive match
- Preserve expansion in parentheses after original: `MTE (Mid-Term Examination)`
- Log unknown acronyms for review (helps build the table over time)

### 1.3 Named Entity Recognizer (`ner.py`)

Uses **rule-based extraction** first; spaCy NER as fallback for complex cases.

**Entities extracted**:

| Entity type | Examples | Extraction method |
|---|---|---|
| `faculty_name` | "Dr. Sharma", "Prof. Gupta" | Regex: `(Dr\.|Prof\.|Mr\.|Ms\.)\s+[A-Z][a-z]+` |
| `course_code` | "CSE339", "ECE201" | Regex: `[A-Z]{2,4}\d{3,4}` |
| `department` | "Computer Science", "Mechanical" | Known-department lookup list |
| `semester` | "7th semester", "Sem 3" | Regex + number normalization |
| `exam_type` | "MTE", "ETE", "CA" | Acronym table after expansion |
| `building_block` | "Block 34", "34B" | Regex: `(Block\s+\d+[A-Z]?)` |

### 1.4 Spell Corrector (`spell_corrector.py`)

Lightweight edit-distance correction for common misspellings. Uses `pyspellchecker` or a domain-specific word list. Only correct if confidence is high (edit distance = 1, high frequency word).

Do not autocorrect proper nouns (faculty names, course codes). Let the NER run after spell correction.

---

## Input/Output Contract

### Input

```python
@dataclass
class RawQuery:
    text: str           # Up to 2000 chars
    session_id: str     # Optional browser session UUID
    timestamp: datetime
```

### Output

```python
@dataclass
class ProcessedQuery:
    original_text: str
    normalized_text: str
    display_text: str           # Original with acronyms expanded inline
    entities: QueryEntities
    processing_latency_ms: int
    timestamp: datetime

@dataclass
class QueryEntities:
    faculty_names: list[str]
    course_codes: list[str]
    departments: list[str]
    semesters: list[str]
    exam_types: list[str]
    building_blocks: list[str]
    acronyms_expanded: list[tuple[str, str]]  # (original, expansion)
```

---

## Configuration (`config/acronyms.yaml`)

```yaml
acronyms:
  MTE: "Mid-Term Examination"
  ETE: "End-Term Examination"
  CA: "Continuous Assessment"
  RP: "Re-appear Exam"
  # ... expandable

department_names:
  - "Computer Science & Engineering"
  - "Electronics & Communication Engineering"
  - "Mechanical Engineering"
  # ... add all LPU departments
```

---

## Tests (`tests/unit/test_preprocessing.py`)

| Test | Input | Expected output |
|---|---|---|
| `test_acronym_expansion_mte` | `"when is MTE?"` | `normalized contains "mid-term examination"` |
| `test_faculty_entity_extraction` | `"Where is Dr. Sharma's cabin?"` | `entities.faculty_names == ["Sharma"]` |
| `test_course_code_extraction` | `"CSE339 assignment submission"` | `entities.course_codes == ["CSE339"]` |
| `test_html_stripping` | `"<b>fee</b> deadline"` | `normalized == "fee deadline"` |
| `test_max_length_truncation` | 2001-char string | truncated to 2000 |
| `test_empty_query` | `""` | `ValueError` raised |
| `test_acronym_not_in_proper_noun` | `"Visit USA"` | `"USA"` not expanded |
