# Module 5 — Dynamic Knowledge Ingestion & TTL Manager

> **Location**: `src/ttl_manager/`
> **Purpose**: Accept new documents, manage their lifecycle (approval, validity, supersession, expiry), and ensure only current, approved content reaches the RAG index.

---

## Responsibility

This module is the **gatekeeper** between raw documents and the live retrieval system. It enforces:

1. **Admin approval gate** — No document enters RAG without explicit admin sign-off
2. **TTL enforcement** — Documents outside their validity window are excluded from retrieval
3. **Supersession management** — When a newer circular replaces an older one, the old one is marked superseded
4. **Audit trail** — Every state change is logged with who did it and when

---

## Document Lifecycle State Machine

```
                  ┌─────────────────────┐
                  │                     │
  Upload/Crawl    │   pending_review    │
  ───────────────▶│                     │
                  └──────┬──────┬───────┘
                         │      │
               Admin     │      │ Admin
               approves  │      │ rejects
                         ▼      ▼
             ┌──────────────┐  ┌──────────┐
             │   approved   │  │ rejected │ (terminal)
             └──────┬───────┘  └──────────┘
                    │
              Extraction + embedding
              succeeds
                    │
                    ▼
             ┌──────────────┐
             │    active    │◀────── Normal retrieval state
             └──┬───────┬───┘
                │       │
    valid_until │       │ Newer version
    passed      │       │ uploaded + confirmed
                ▼       ▼
          ┌─────────┐  ┌────────────┐
          │ expired │  │ superseded │
          └─────────┘  └────────────┘
          (both: removed from Qdrant; original preserved on Drive for audit)
```

---

## Sub-Components

### 5.1 Document Intake (`intake.py`)

```python
async def intake_document(
    file_bytes: bytes,
    claimed_mime_type: str,
    filename: str,
    source_url: str | None,
    category: str,
    crawl_run_id: str | None
) -> IntakeResult:
    
    # 1. Verify file signature (magic bytes) matches claimed MIME
    verified_mime = detect_mime(file_bytes)
    if verified_mime != claimed_mime_type:
        raise MimeMismatchError(...)
    
    # 2. Compute SHA-256
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    
    # 3. Check for duplicate
    existing = db.query("SELECT id FROM knowledge.documents WHERE sha256 = :h", h=sha256)
    if existing:
        return IntakeResult(status="duplicate", existing_id=existing.id)
    
    # 4. Sanitize filename (prevent path traversal)
    safe_filename = sanitize_filename(filename)
    
    # 5. Upload to Google Drive (raw/ subfolder)
    drive_result = await drive_uploader.upload(file_bytes, safe_filename, category)
    
    # 6. Insert into PostgreSQL with status = pending_review
    doc_id = db.insert_document(
        sha256=sha256, filename=safe_filename,
        drive_file_id=drive_result.file_id,
        drive_url=drive_result.shareable_url,
        source_url=source_url, category=category,
        content_type=verified_mime,
        status="pending_review", crawl_run_id=crawl_run_id
    )
    
    return IntakeResult(status="accepted", document_id=doc_id)
```

### 5.2 Admin Approval (`approval.py`)

```python
async def approve_document(
    document_id: str,
    approved_by: str,
    title: str,
    category: str,
    valid_from: date | None,
    valid_until: date | None,
    supersedes_document_id: str | None,
    verification_notes: str
) -> ApprovalResult:
    
    # Validate supersession claim
    if supersedes_document_id:
        old_doc = db.get_document(supersedes_document_id)
        if not old_doc or old_doc.status != 'active':
            raise SupersessionError("Cannot supersede a document that is not active")
    
    # Update document status
    db.update_document(document_id,
        status="approved",
        title=title, category=category,
        valid_from=valid_from, valid_until=valid_until,
        supersedes_document_id=supersedes_document_id,
        admin_approved_by=approved_by,
        admin_approved_at=datetime.utcnow(),
        verification_notes=verification_notes
    )
    
    # Trigger async extraction pipeline
    await extraction_pipeline.enqueue(document_id)
    
    return ApprovalResult(status="approved", next="extraction_queued")
```

### 5.3 Extraction Pipeline (`extractor.py`)

```python
async def extract_and_index(document_id: str):
    doc = db.get_document(document_id)
    file_bytes = await drive_downloader.download(doc.drive_file_id)
    
    # Extract text based on MIME type
    if doc.content_type == "application/pdf":
        text = extract_pdf(file_bytes)      # PyMuPDF
    elif "wordprocessingml" in doc.content_type:
        text = extract_docx(file_bytes)
    elif "spreadsheetml" in doc.content_type:
        text = extract_xlsx(file_bytes)
    else:
        text = extract_plaintext(file_bytes)
    
    if not text or len(text.strip()) < 50:
        # Try OCR fallback
        text = ocr_extract(file_bytes)
        extraction_quality = "ocr_used" if text else "failed"
    else:
        extraction_quality = "good"
    
    if not text:
        db.update_document(document_id, status="rejected",
                          verification_notes="Extraction failed; document may be image-only")
        return
    
    # Chunk text
    chunks = chunk_text(text, max_tokens=512, overlap=64)
    
    # Embed and index in Qdrant
    for i, chunk in enumerate(chunks):
        embedding = embed(chunk)
        point_id = uuid4()
        
        qdrant.upsert(collection=get_collection(doc.category), points=[{
            "id": str(point_id),
            "vector": embedding,
            "payload": {
                "document_id": str(doc.id),
                "chunk_id": str(point_id),
                "chunk_index": i,
                "chunk_text": chunk,
                "document_title": doc.title,
                "category": doc.category,
                "source_url": doc.source_url,
                "drive_url": doc.drive_url,
                "valid_from": str(doc.valid_from) if doc.valid_from else None,
                "valid_until": str(doc.valid_until) if doc.valid_until else "9999-12-31",
                "status": "active",
                "approved": True,
                "embedding_model": EMBEDDING_MODEL
            }
        }])
        
        db.insert_chunk(document_id, i, chunk, str(point_id))
    
    # Mark document as active
    db.update_document(document_id, 
                      status="active",
                      extraction_quality=extraction_quality,
                      embedding_model_version=EMBEDDING_MODEL)
    
    # If superseding, deactivate old document
    if doc.supersedes_document_id:
        await deactivate_document(doc.supersedes_document_id, reason="superseded")
```

### 5.4 TTL Expiry Sweep (`ttl_sweep.py`)

Runs nightly at 00:30 via APScheduler.

```python
async def ttl_expiry_sweep():
    expired_docs = db.query("""
        SELECT id FROM knowledge.documents
        WHERE status = 'active'
          AND valid_until IS NOT NULL
          AND valid_until < CURRENT_DATE
    """)
    
    for doc in expired_docs:
        await deactivate_document(doc.id, reason="expired")
    
    logger.info(f"TTL sweep complete: {len(expired_docs)} documents expired")
```

---

## Filename Sanitization Rules

```python
def sanitize_filename(filename: str) -> str:
    # 1. Remove path separators (prevent traversal)
    filename = filename.replace("/", "_").replace("\\", "_").replace("..", "_")
    # 2. Keep only safe characters
    filename = re.sub(r'[^\w\-_\. ]', '_', filename)
    # 3. Limit length
    stem, ext = os.path.splitext(filename)
    return stem[:200] + ext
```

---

## Tests (`tests/unit/test_ttl_manager.py`)

| Test | Scenario | Expected |
|---|---|---|
| `test_duplicate_sha256_rejected` | Same file uploaded twice | Second upload returns "duplicate" |
| `test_pending_not_retrievable` | Document in pending_review | RAG search never returns it |
| `test_expiry_sweep_deactivates` | Document with past valid_until | Sweep marks as expired; removed from Qdrant |
| `test_supersession_deactivates_old` | New doc supersedes old | Old doc marked superseded; removed from Qdrant |
| `test_supersession_requires_active_target` | Supersede a rejected doc | Error raised |
| `test_path_traversal_filename` | Filename `../../etc/passwd.pdf` | Sanitized to safe name |
| `test_mime_mismatch_rejected` | DOCX with PDF extension | MimeMismatchError |
| `test_extraction_failed_rejected` | Image-only PDF with no OCR | Document rejected with note |
