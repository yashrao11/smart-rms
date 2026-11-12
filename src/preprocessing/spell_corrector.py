"""Spell correction sub-component for query preprocessing."""

import logging
import re
from typing import Iterable, Optional, Set
from spellchecker import SpellChecker

logger = logging.getLogger(__name__)

COMMON_INDIAN_NAMES: Set[str] = {
    # First names
    "rajesh", "amit", "rahul", "priya", "pooja", "neha", "rohit", "vikas",
    "suresh", "ramesh", "manish", "praveen", "deepak", "sunil", "anil",
    "sanjay", "ajay", "vijay", "harpreet", "gurpreet", "jaspreet", "aman",
    "simran", "anita", "sunita", "kavita", "meenakshi", "sandhya", "divya",
    "shweta", "swati", "alok", "ashok", "arun", "varun", "tarun", "gaurav",
    "saurabh", "ankit", "sumit", "siddharth", "abhishek", "vivek", "mayank",
    "nikhil", "kunal", "pankaj", "pradeep", "kuldeep", "navdeep", "yash",
    # Surnames
    "sharma", "gupta", "singh", "kumar", "verma", "patel", "rao", "kaur",
    "reddy", "mehta", "jain", "yadav", "nair", "mishra", "bose", "sen",
    "das", "pandey", "tiwari", "jha", "choudhary", "bhatia", "malhotra",
    "aggarwal", "agarwal", "saxena", "joshi", "shukla", "tripathi",
}

DEFAULT_WHITELIST: Set[str] = COMMON_INDIAN_NAMES.union({
    # University acronyms & identifiers
    "mte", "ete", "ca", "rp", "ums", "lpu", "cse", "ece", "rms", "hod", "dsw",
    "coe", "drc", "gpa", "sgpa", "cgpa", "od", "mcq",
    # Campus terms
    "cabin", "hostel", "warden", "block", "syllabus", "syllabi", "curriculum",
    "timetable", "reappear", "attendance", "proctor",
    # Titles
    "dr", "prof", "mr", "ms", "mrs", "er",
})


def _levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


class SpellCorrector:
    """Lightweight spell corrector that preserves proper nouns, acronyms, and course codes."""

    def __init__(self, additional_whitelist: Optional[Iterable[str]] = None):
        self.spell = SpellChecker()
        self.whitelist: Set[str] = set(DEFAULT_WHITELIST)
        if additional_whitelist:
            for word in additional_whitelist:
                self.whitelist.add(word.lower())

        # Seed spell checker with whitelist words so they are recognized as valid
        self.spell.word_frequency.load_words(list(self.whitelist))

    def correct(self, text: str) -> str:
        """Correct misspelled words in text with high confidence (edit distance <= 1).

        Preserves:
        - Words with digits (e.g. CSE339, 34B)
        - Acronyms (e.g. MTE, ETE)
        - Proper nouns / title-following words (e.g. Dr. Rajesh Sharma)
        - Real names before recognized surnames (e.g. Rajesh Sharma)
        - Words in the whitelist
        """
        if not text:
            return text

        tokens = re.split(r"(\s+|[^\w\s])", text)
        corrected_tokens = []
        in_title_context = False

        for i, token in enumerate(tokens):
            if not token:
                continue

            # Whitespace does not reset title context
            if token.isspace():
                corrected_tokens.append(token)
                continue

            # Punctuation
            if re.match(r"^[^\w\s]+$", token):
                corrected_tokens.append(token)
                # Period or colon right after a title (e.g. "Dr.") preserves title context
                if token in {".", ":"}:
                    pass
                else:
                    in_title_context = False
                continue

            # Tokens containing digits or underscores (course codes like CSE339, blocks like 34B)
            if re.search(r"[\d_]", token):
                corrected_tokens.append(token)
                in_title_context = False
                continue

            lower_token = token.lower()

            # Check if this word is a title
            if lower_token in {"dr", "prof", "mr", "ms", "mrs", "er"}:
                corrected_tokens.append(token)
                in_title_context = True
                continue

            # Lookahead: is the next non-space word a known surname?
            is_followed_by_surname = False
            for j in range(i + 1, min(i + 4, len(tokens))):
                future_tok = tokens[j]
                if future_tok.isspace():
                    continue
                if future_tok.lower() in COMMON_INDIAN_NAMES:
                    is_followed_by_surname = True
                break

            # Don't autocorrect if:
            # 1. Inside title context and capitalized (part of a person's name)
            # 2. Followed by a known surname (first name in a real name)
            # 3. Token is in whitelist
            # 4. Token is all uppercase acronym (2+ letters)
            # 5. Token is already correctly spelled in dictionary
            if (
                (in_title_context and token[0].isupper())
                or (token[0].isupper() and is_followed_by_surname)
                or lower_token in self.whitelist
                or (token.isupper() and len(token) >= 2)
                or lower_token in self.spell
            ):
                corrected_tokens.append(token)
                # Keep title context active for multi-word names (e.g. "Dr. Amit Sharma")
                if not token[0].isupper():
                    in_title_context = False
                continue

            in_title_context = False

            # Candidate lookup for misspelled words
            candidate = self.spell.correction(lower_token)
            if candidate and candidate != lower_token:
                dist = _levenshtein(lower_token, candidate)
                if dist <= 1:
                    if token.isupper():
                        candidate = candidate.upper()
                    elif token[0].isupper():
                        candidate = candidate.capitalize()
                    corrected_tokens.append(candidate)
                    continue

            # Fallback to original token
            corrected_tokens.append(token)

        return "".join(corrected_tokens)
