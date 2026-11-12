"""Named Entity Recognition sub-component for university queries."""

import re
from typing import Dict, List, Optional, Set
from .models import QueryEntities

FACULTY_TITLES = r"(?:Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.|Er\.|Dr|Prof|Mr|Ms|Mrs|Er)"

# Non-name words that might follow a title or name in a sentence
NON_NAME_WORDS: Set[str] = {
    "Cabin", "Office", "Room", "Lab", "Block", "Floor", "Department",
    "Sir", "Madam", "Exam", "Class", "Lecture", "Schedule", "Hours",
    "Building", "University", "College", "Lpu", "School", "Center", "Centre"
}

# Common surnames and family names in Indian / university faculty contexts
COMMON_SURNAMES: Set[str] = {
    "sharma", "gupta", "singh", "kumar", "verma", "patel", "rao", "kaur",
    "reddy", "mehta", "jain", "yadav", "nair", "mishra", "bose", "sen",
    "das", "pandey", "tiwari", "jha", "choudhary", "bhatia", "malhotra",
    "aggarwal", "agarwal", "saxena", "joshi", "shukla", "tripathi",
}

# Regex matching title followed by full real name (1 to 3 capitalized words)
# e.g., "Dr. Amit Sharma", "Prof. Rajesh Kumar Verma", "Dr. Sharma"
FACULTY_TITLE_PATTERN = re.compile(
    rf"\b{FACULTY_TITLES}\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){{0,2}})(?:['’]s)?\b"
)

# Regex matching full real names without title when ending in known faculty surname
# e.g., "Amit Sharma's cabin", "Rajesh Kumar"
FACULTY_NO_TITLE_PATTERN = re.compile(
    r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){1,2})(?:['’]s)?\b"
)

# Course code: 2-4 letters followed by 3-4 digits, e.g. CSE339, ECE201
COURSE_CODE_PATTERN = re.compile(r"\b([A-Za-z]{2,4}\d{3,4}[A-Za-z]?)\b")

# Semester: "7th semester", "Sem 3", "semester 4", "1st sem"
SEMESTER_PATTERN = re.compile(
    r"\b(?:sem(?:ester)?\s*(\d{1,2})|(\d{1,2})(?:st|nd|rd|th)?\s*sem(?:ester)?)\b",
    re.IGNORECASE,
)

# Exam types: MTE, ETE, CA, RP
EXAM_TYPE_PATTERN = re.compile(r"\b(MTE|ETE|CA|RP)\b", re.IGNORECASE)

# Building block: "Block 34", "Block 34A", "34B"
BUILDING_BLOCK_PATTERN = re.compile(
    r"\b(Block\s+\d{1,3}[A-Za-z]?|\b\d{1,3}[A-Za-z]\b)",
    re.IGNORECASE,
)

DEFAULT_DEPARTMENTS = [
    "Computer Science & Engineering",
    "Electronics & Communication Engineering",
    "Mechanical Engineering",
    "Civil Engineering",
    "Electrical Engineering",
    "Biotechnology",
    "Management",
    "Commerce",
    "Pharmacy",
    "Law",
    "Design",
    "Hotel Management",
    "Agriculture",
    "Computer Science",
    "Information Technology",
]


class NamedEntityRecognizer:
    """Extracts domain-specific entities using rules and regex."""

    def __init__(self, known_departments: Optional[List[str]] = None):
        self.departments = known_departments or DEFAULT_DEPARTMENTS.copy()

    def _clean_faculty_name(self, raw_name: str) -> Optional[str]:
        """Strip trailing non-name tokens (like 'Cabin') and possessives."""
        cleaned = re.sub(r"['’]s$", "", raw_name).strip()
        words = cleaned.split()
        # Drop trailing capitalized non-name words (e.g. 'Cabin' in 'Dr. Amit Sharma Cabin')
        while words and words[-1].capitalize() in NON_NAME_WORDS:
            words.pop()
        if words:
            return " ".join(words)
        return None

    def extract(
        self,
        text: str,
        acronyms_expanded: Optional[List[tuple[str, str]]] = None,
    ) -> QueryEntities:
        """Extract all supported entity types from query text."""
        entities = QueryEntities()

        if not text:
            return entities

        if acronyms_expanded:
            entities.acronyms_expanded = list(acronyms_expanded)

        # 1. Faculty Full Name Extraction (with Title)
        for match in FACULTY_TITLE_PATTERN.finditer(text):
            clean_name = self._clean_faculty_name(match.group(1))
            if clean_name and clean_name not in entities.faculty_names:
                entities.faculty_names.append(clean_name)

        # 2. Faculty Real Name Extraction (without Title, e.g. "Amit Sharma")
        for match in FACULTY_NO_TITLE_PATTERN.finditer(text):
            raw_match = match.group(1)
            words = raw_match.split()
            # If the phrase ends in a known surname and contains no stop words
            if (
                len(words) >= 2
                and words[-1].lower() in COMMON_SURNAMES
                and all(w.capitalize() not in NON_NAME_WORDS for w in words)
            ):
                clean_name = self._clean_faculty_name(raw_match)
                if clean_name and clean_name not in entities.faculty_names:
                    # Check if already covered by title-based match (e.g. substring)
                    if not any(clean_name in existing for existing in entities.faculty_names):
                        entities.faculty_names.append(clean_name)

        # 3. Course Code Extraction (normalized to uppercase)
        for match in COURSE_CODE_PATTERN.finditer(text):
            code = match.group(1).upper()
            if code not in entities.course_codes:
                entities.course_codes.append(code)

        # 4. Department Extraction
        for dept in self.departments:
            pattern = re.compile(rf"\b{re.escape(dept)}\b", re.IGNORECASE)
            if pattern.search(text):
                if dept not in entities.departments:
                    entities.departments.append(dept)

        # 5. Semester Extraction
        for match in SEMESTER_PATTERN.finditer(text):
            num_str = match.group(1) or match.group(2)
            if num_str:
                sem_num = int(num_str)
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(
                    sem_num if (sem_num < 20) else sem_num % 10, "th"
                )
                normalized_sem = f"{sem_num}{suffix} Semester"
                if normalized_sem not in entities.semesters:
                    entities.semesters.append(normalized_sem)

        # 6. Exam Type Extraction (from text and expanded acronyms)
        for match in EXAM_TYPE_PATTERN.finditer(text):
            exam = match.group(1).upper()
            if exam not in entities.exam_types:
                entities.exam_types.append(exam)

        if acronyms_expanded:
            for original, _ in acronyms_expanded:
                orig_upper = original.upper()
                if orig_upper in {"MTE", "ETE", "CA", "RP"} and orig_upper not in entities.exam_types:
                    entities.exam_types.append(orig_upper)

        # 7. Building Block Extraction
        for match in BUILDING_BLOCK_PATTERN.finditer(text):
            raw_block = match.group(1).strip()
            if raw_block.lower().startswith("block"):
                normalized_block = "Block " + raw_block[5:].strip().upper()
            else:
                normalized_block = raw_block.upper()
            if normalized_block not in entities.building_blocks:
                entities.building_blocks.append(normalized_block)

        return entities
