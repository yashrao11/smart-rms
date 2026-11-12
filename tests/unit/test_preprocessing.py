"""Unit tests for Module 1 — Query Preprocessing."""

import pytest
from src.preprocessing import Preprocessor, RawQuery, clean_text, normalize


@pytest.fixture
def preprocessor():
    """Fixture providing an initialized Preprocessor."""
    return Preprocessor()


def test_acronym_expansion_mte(preprocessor):
    """Test that university acronyms like MTE are expanded."""
    query = "when is MTE?"
    res = preprocessor.process(query)
    assert "mid-term examination" in res.normalized_text
    assert ("MTE", "Mid-Term Examination") in res.entities.acronyms_expanded


def test_faculty_entity_extraction_full_name(preprocessor):
    """Test extracting full real faculty name with title and possessive."""
    query = "Where is Dr. Amit Sharma's cabin?"
    res = preprocessor.process(query)
    assert res.entities.faculty_names == ["Amit Sharma"]


def test_faculty_entity_extraction_three_part_name(preprocessor):
    """Test extracting three-part real faculty name."""
    query = "When can I meet Prof. Rajesh Kumar Verma in Block 34?"
    res = preprocessor.process(query)
    assert res.entities.faculty_names == ["Rajesh Kumar Verma"]


def test_faculty_entity_extraction_without_title(preprocessor):
    """Test extracting real faculty name even without title 'Dr.'."""
    query = "Where is Amit Sharma's cabin?"
    res = preprocessor.process(query)
    assert res.entities.faculty_names == ["Amit Sharma"]


def test_faculty_entity_extraction_fallback_surname(preprocessor):
    """Test fallback when student only knows title + surname."""
    query = "Where is Dr. Sharma's cabin?"
    res = preprocessor.process(query)
    assert res.entities.faculty_names == ["Sharma"]


def test_course_code_extraction(preprocessor):
    """Test extracting university course code."""
    query = "CSE339 assignment submission"
    res = preprocessor.process(query)
    assert "CSE339" in res.entities.course_codes


def test_html_stripping(preprocessor):
    """Test stripping HTML tags from pasted input."""
    raw = "<b>fee</b> deadline"
    assert clean_text(raw) == "fee deadline"
    assert normalize(raw) == "fee deadline"

    res = preprocessor.process(raw)
    assert res.normalized_text == "fee deadline"


def test_max_length_truncation(preprocessor):
    """Test that queries exceeding 2000 chars are truncated to 2000."""
    long_query = "a" * 2001
    cleaned = clean_text(long_query)
    assert len(cleaned) == 2000

    res = preprocessor.process(long_query)
    assert len(res.original_text) == 2001
    assert len(res.normalized_text) <= 2000


def test_empty_query(preprocessor):
    """Test that empty queries raise a ValueError."""
    with pytest.raises(ValueError, match="Query cannot be empty"):
        preprocessor.process("")

    with pytest.raises(ValueError, match="Query cannot be empty"):
        preprocessor.process("    ")


def test_acronym_not_in_proper_noun(preprocessor):
    """Test that non-university acronyms like USA are not expanded."""
    query = "Visit USA"
    res = preprocessor.process(query)
    assert "USA" not in [acronym for acronym, _ in res.entities.acronyms_expanded]
    assert "usa" in res.normalized_text


def test_semester_and_exam_extraction(preprocessor):
    """Test extraction of semester and exam type."""
    query = "When is 7th semester ETE exam?"
    res = preprocessor.process(query)
    assert "7th Semester" in res.entities.semesters
    assert "ETE" in res.entities.exam_types


def test_building_block_extraction(preprocessor):
    """Test extraction of campus building blocks."""
    query = "Where is room 201 in Block 34?"
    res = preprocessor.process(query)
    assert "Block 34" in res.entities.building_blocks


def test_spell_correction(preprocessor):
    """Test correcting typos while preserving real names and course codes."""
    query = "submisson date for CSE339 with Dr. Amit Sharma"
    res = preprocessor.process(query)
    # Typo 'submisson' should be corrected to 'submission'
    assert "submission" in res.normalized_text
    # Proper real name and course code must be preserved intact
    assert "CSE339" in res.entities.course_codes
    assert "Amit Sharma" in res.entities.faculty_names


def test_processing_latency(preprocessor):
    """Test that latency meets the < 100ms requirement."""
    res = preprocessor.process("Where is Dr. Gupta's office in Block 38?")
    assert res.processing_latency_ms < 100
