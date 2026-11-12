"""Text normalization sub-component for query preprocessing."""

import re
import unicodedata

HTML_TAG_PATTERN = re.compile(r"<[^>]+?>")
MULTIPLE_SPACES_PATTERN = re.compile(r"\s+")
MAX_QUERY_LENGTH = 2000


def clean_text(raw_query: str, max_length: int = MAX_QUERY_LENGTH) -> str:
    """Clean text while preserving case.

    1. Enforce string type and validate non-empty
    2. Truncate at max_length (default: 2000 characters)
    3. Remove HTML tags if accidentally pasted
    4. Normalize Unicode to NFC form
    5. Remove non-printable control characters
    6. Collapse multiple spaces to a single space
    7. Strip leading and trailing whitespace
    """
    if not isinstance(raw_query, str):
        raise ValueError("Query must be a string")

    # 1. Truncate at max length
    truncated = raw_query[:max_length]

    # Validate non-empty
    if not truncated.strip():
        raise ValueError("Query cannot be empty")

    # 2. Remove HTML tags
    no_html = HTML_TAG_PATTERN.sub(" ", truncated)

    # 3. Normalize Unicode (NFC form)
    nfc_text = unicodedata.normalize("NFC", no_html)

    # 4. Remove control characters (category 'C' in Unicode, allowing standard spaces)
    cleaned_chars = [
        ch if (not unicodedata.category(ch).startswith("C") or ch in "\n\r\t ") else " "
        for ch in nfc_text
    ]
    no_control = "".join(cleaned_chars)

    # 5. Collapse spaces and strip
    collapsed = MULTIPLE_SPACES_PATTERN.sub(" ", no_control).strip()

    if not collapsed:
        raise ValueError("Query cannot be empty")

    return collapsed


def normalize(raw_query: str, max_length: int = MAX_QUERY_LENGTH) -> str:
    """Normalize raw query to lowercase standardized form for downstream processing.

    Follows the 7-step specification from docs/modules/01_preprocessing.md.
    """
    cleaned = clean_text(raw_query, max_length=max_length)
    return cleaned.lower()
