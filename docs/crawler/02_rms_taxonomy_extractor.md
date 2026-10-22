# RMS Taxonomy Extractor — Design & Extraction Plan

> **Status**: Pre-implementation plan — No code written, no crawling started, no credentials used.
> **Purpose**: Read the exact LPU RMS category hierarchy from the authorized UI and export it to PostgreSQL and CSV.

---

## 1. What We Are Extracting

The LPU RMS ticket form contains cascading dependent dropdowns:

```
Message Type
  └── Category Type
        └── Master Category
              └── Category
                    └── Subcategory (may or may not exist)
                          └── (Deeper levels if present)
                                └── Dealing Person (auto-assigned at some level)
```

**What we do NOT know yet** (until extraction runs):
- Exact labels for every Message Type
- Depth of each branch (some may stop at Category; others may have Subcategory or deeper)
- At which level the dealing person is assigned (not assumed to be the leaf)
- Whether the same dealing person appears at multiple nodes
- Whether RMS uses numeric IDs, slugs, or labels as option values

**Extraction goal**: A complete, unambiguous map of every path from Message Type to the deepest available category, with the associated dealing person at whatever level it is assigned.

---

## 2. Authorization and Prerequisites

> [!IMPORTANT]
> Before any extraction script runs, confirm that:
> 1. Your project supervisor has approved this as a capstone deliverable.
> 2. LPU's IT policy permits reading the RMS UI programmatically via an authorized account.
> 3. Preferred approach: Request an official export of the RMS category lookup tables and routing assignments from the university administration. If an admin/mentor can provide a CSV or database export, use that instead of any automated extraction.

**Preferred flow** (in priority order):

| Priority | Method | When to use |
|---|---|---|
| 1 | Official admin/mentor export from RMS database | If university IT can provide lookup table exports |
| 2 | Manual enumeration via the RMS UI | If you can access the form and manually record all options |
| 3 | Playwright-based UI reader (this document) | Only if the above are impractical due to the volume of combinations |

---

## 3. Playwright Extractor Design

### 3.1 What It Does

- Opens a Playwright browser in **headed (visible) mode**
- Waits for the **human account owner to log in manually** through the standard LPU UMS login page
- Once logged in, navigates to the RMS ticket creation form
- Iterates through every combination of dropdown options
- Records each hierarchy path and the dealing person shown
- **Does NOT submit any form, create any ticket, or interact with anything other than reading dropdown values**
- Runs in **DRY-RUN / DISCOVERY mode by default** — only reports what it finds, does not write to any database

### 3.2 What It Never Does

| Action | Status |
|---|---|
| Automate UMS login | ❌ Never |
| Store or accept credentials | ❌ Never |
| Bypass CAPTCHA | ❌ Never |
| Submit a ticket or form | ❌ Never |
| Read other students' data | ❌ Never |
| Access URLs not in the approved allowlist | ❌ Never |
| Write to the RMS system | ❌ Never |
| Click payment or profile links | ❌ Never |

---

## 4. Human Login Flow (Required Before Any Extraction)

```
1. Run: python scripts/rms_extract_discover.py --mode=login
2. A VISIBLE Chromium browser window opens
3. You (the account owner) navigate to https://ums.lpu.in/
4. You type your credentials and solve the CAPTCHA yourself
5. You navigate to the RMS ticket creation page
6. You press ENTER in the terminal to signal "I am logged in and on the form page"
7. The script saves the browser context to .playwright_session/rms_session.json
8. The browser remains open; the script takes over navigation within the form only
```

The script never sees your password. It receives a live browser context already authenticated.

---

## 5. Dropdown Iteration Algorithm

```
ALGORITHM: RMS Hierarchy Traversal

Input: Authenticated browser on RMS ticket creation form
Output: rms_taxonomy_inventory.csv + dry-run report

1. Identify all top-level options in the "Message Type" dropdown
   Record: option_text, option_value (the HTML value="" attribute)
   
2. For each Message Type option MT:
   a. Select MT in the dropdown
   b. Wait for "Category Type" dropdown to update (waitForNetworkIdle or MutationObserver)
   c. Record all Category Type options visible
   d. If no options appear → mark MT as having no children; log as "leaf" or "blocked"
   
   For each Category Type option CT:
     a. Select CT
     b. Wait for "Master Category" dropdown to update
     c. Record all Master Category options
     
     For each Master Category option MC:
       a. Select MC
       b. Wait for "Category" dropdown to update
       c. Record all Category options
       d. Check if "Dealing Person" field has already populated → record it NOW
          (assignment may be at Master Category level)
       
       For each Category option C:
         a. Select C
         b. Wait for any "Subcategory" dropdown or "Dealing Person" to update
         c. Record Subcategory options if present
         d. Record Dealing Person value if present/changed
         
         For each Subcategory option SC (if present):
           a. Select SC
           b. Wait for deeper options or Dealing Person update
           c. Record Dealing Person value
           d. Continue recursion if deeper levels appear
           
         If no Subcategory: record path as complete at Category level
   
3. After all combinations: export to CSV and print dry-run summary

POLITE DELAYS:
  - 1.5 seconds after each dropdown selection (configurable)
  - If a request fails: wait 5 seconds, retry once, then mark as error and continue
  
VISITED TRACKING:
  - Never re-select the same combination (path-based deduplication)
```

### 5.1 Detecting Dropdown Updates

UMS is a JavaScript SPA. After selecting a value, the dependent dropdown may update via AJAX. Detection strategy:

```python
# After selecting a parent dropdown option:
await page.select_option("#messageType", value=mt_value)

# Strategy 1: Wait for network idle (safest for AJAX-heavy SPAs)
await page.wait_for_load_state("networkidle", timeout=10000)

# Strategy 2: Wait for the child dropdown to have more than 1 option
await page.wait_for_function(
    "document.querySelector('#categoryType').options.length > 1",
    timeout=10000
)

# If timeout → the child has no options for this parent → log as childless node
```

---

## 6. Output: `rms_taxonomy_inventory.csv`

All columns are populated from what the extractor observes. **Never invent or guess a value.**

| Column | Type | Notes |
|---|---|---|
| `document_id` | UUID | Auto-generated per row |
| `message_type` | string | Exact label from dropdown |
| `category_type` | string or NULL | NULL if not present for this path |
| `master_category` | string or NULL | NULL if not present |
| `category` | string or NULL | NULL if not present |
| `subcategory` | string or NULL | NULL if not present |
| `full_path` | string | Pipe-delimited: `MT \| CT \| MC \| C \| SC` |
| `rms_option_id` | string or NULL | HTML `value=""` attribute of the deepest selected option; NULL if attribute absent |
| `parent_option_id` | string or NULL | HTML `value=""` attribute of the parent option |
| `hierarchy_level` | integer | 1=MessageType, 2=CategoryType, 3=MasterCategory, 4=Category, 5=Subcategory, 6+=deeper |
| `dealing_person_name` | string or NULL | Exact text from the Dealing Person field; NULL if not populated at this node |
| `dealing_person_id` | string or NULL | HTML value of Dealing Person field; NULL if absent |
| `official_contact_if_authorized` | string or NULL | Contact shown in authorized UI only; NULL if not shown |
| `source_page` | string | URL of the RMS form where this was observed |
| `verified_at` | ISO8601 | Timestamp when this row was extracted |
| `active_status` | boolean | TRUE for all extracted rows; set to FALSE manually if found to be outdated |
| `notes` | string | Any ambiguity, extraction error, or manual reviewer note |

### Example rows (illustrative — not real LPU data):

```csv
document_id,message_type,category_type,master_category,category,subcategory,full_path,rms_option_id,parent_option_id,hierarchy_level,dealing_person_name,dealing_person_id,official_contact_if_authorized,source_page,verified_at,active_status,notes
uuid-001,Academic,Examination,Grade Query,Re-evaluation Request,,Academic|Examination|Grade Query|Re-evaluation Request,opt_42,opt_31,4,Dr. Example Name,dp_07,,https://ums.lpu.in/.../rms_form,2026-10-22T19:00:00+05:30,TRUE,
uuid-002,Academic,Examination,Grade Query,Re-evaluation Request,Practical Component,Academic|...|Practical Component,opt_43,opt_42,5,Dr. Example Name,dp_07,,https://ums.lpu.in/.../rms_form,2026-10-22T19:00:00+05:30,TRUE,Dealing person same as parent
uuid-003,Fee Related,,,,,Fee Related,opt_12,,1,,,,https://ums.lpu.in/.../rms_form,2026-10-22T19:00:00+05:30,TRUE,Dealing person appears at MessageType level for this branch
```

> **NULL vs. empty string**: Use explicit NULL (empty cell in CSV) to mean "this field is not present or not observed." An empty string would mean "present but blank." These are different.

---

## 7. PostgreSQL Import

After the CSV is reviewed and human-verified, import with the dedicated loader:

```
python scripts/import_rms_taxonomy.py \
  --csv data/metadata/rms_taxonomy_inventory.csv \
  --dry-run     # Preview what would be inserted; no DB writes
  
python scripts/import_rms_taxonomy.py \
  --csv data/metadata/rms_taxonomy_inventory.csv \
  --confirm     # Actually write to rms_taxonomy schema
```

The loader:
1. Creates all `message_types` rows
2. Creates `taxonomy_nodes` rows in level order (parents before children)
3. Creates `dealing_persons` rows (deduplicated by `rms_person_id` or `display_name`)
4. Creates `routing_assignments` at the level where each dealing person was observed
5. Reports any rows with missing required fields for human review

---

## 8. Dry-Run Report Format

Before any database writes, the extractor produces `data/crawler/discovery_reports/rms_taxonomy_YYYYMMDD.html`:

```
RMS TAXONOMY DISCOVERY REPORT
Run date: 2026-10-22
Mode: DRY-RUN (no database writes, no form submissions)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Summary:
  Message Types discovered:       X
  Total hierarchy paths mapped:   Y
  Paths with dealing person:      Z
  Paths WITHOUT dealing person:   W  ← requires manual review
  Extraction errors:              E
  Ambiguous assignments:          A  ← same node → multiple persons

Top-level Message Types:
  ✓ [Label 1] — N Category Types
  ✓ [Label 2] — M Category Types
  ✗ [Label 3] — TIMEOUT: child dropdown did not update (manual review needed)

Dealing Person Assignments by Level:
  Level 1 (Message Type):     P assignments
  Level 2 (Category Type):    Q assignments
  Level 3 (Master Category):  R assignments
  Level 4 (Category):         S assignments
  Level 5 (Subcategory):      T assignments

Missing/Ambiguous:
  PATH | Reason | Recommended action
  ...

Full hierarchy table: [see attached CSV]
```

---

## 9. Missing Information vs. Confirmed Absence

| Situation | How to record it |
|---|---|
| Dropdown did not appear | `category_type = NULL`, `notes = "dropdown not present for this message type"` |
| Dealing person field empty (no selection made by form yet) | `dealing_person_name = NULL`, `notes = "form did not auto-populate dealing person at this level"` |
| Dropdown appeared but had zero options | `notes = "dropdown appeared but options list was empty"` |
| Request timed out before dropdown updated | `notes = "TIMEOUT: child dropdown update not observed; requires manual verification"` |
| Extraction script error | `notes = "EXTRACTION_ERROR: [error message]"` |

These are recorded in the CSV `notes` column. The human reviewer must resolve each one before importing to PostgreSQL.

---

## 10. Test Cases for the Extractor

| Test | What it verifies |
|---|---|
| `test_dropdown_iteration` | All Message Type options are visited exactly once |
| `test_dealing_person_capture_level` | Dealing person level is recorded at first appearance, not assumed leaf |
| `test_null_vs_empty` | NULL fields are written as empty CSV cells, not empty strings |
| `test_timeout_handling` | Timeout does not crash extractor; marks row with TIMEOUT note |
| `test_no_form_submit` | No POST request is made during entire extraction run |
| `test_session_expiry_detection` | If session expires mid-run, extractor pauses and prompts re-login |
| `test_allowlist_enforcement` | Extractor does not navigate outside the approved RMS form URL |
| `test_csv_path_collision` | Duplicate hierarchy paths are detected and merged, not duplicated |

---

## 11. Files and Locations

| File | Location | Purpose |
|---|---|---|
| Extractor script | `scripts/rms_extract_discover.py` | Main extraction script |
| PostgreSQL importer | `scripts/import_rms_taxonomy.py` | CSV → PostgreSQL loader |
| Output CSV | `data/metadata/rms_taxonomy_inventory.csv` | Extracted hierarchy |
| Discovery report | `data/crawler/discovery_reports/` | HTML dry-run report |
| Session (gitignored) | `.playwright_session/rms_session.json` | Browser auth state |
| Config | `config/rms_extractor_config.yaml` | Selectors, delays, approved URLs |
