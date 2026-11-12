"""Data models for query preprocessing pipeline."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple


@dataclass
class RawQuery:
    """Input query representation."""
    text: str  # Up to 2000 chars
    session_id: Optional[str] = None  # Optional browser session UUID
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class QueryEntities:
    """Extracted entities from query text."""
    faculty_names: List[str] = field(default_factory=list)
    course_codes: List[str] = field(default_factory=list)
    departments: List[str] = field(default_factory=list)
    semesters: List[str] = field(default_factory=list)
    exam_types: List[str] = field(default_factory=list)
    building_blocks: List[str] = field(default_factory=list)
    acronyms_expanded: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class ProcessedQuery:
    """Normalized query output for downstream modules."""
    original_text: str
    normalized_text: str
    display_text: str
    entities: QueryEntities
    processing_latency_ms: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
