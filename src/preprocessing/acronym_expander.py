"""Acronym expansion sub-component for university terminology."""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import yaml

logger = logging.getLogger(__name__)

DEFAULT_ACRONYMS: Dict[str, str] = {
    "MTE": "Mid-Term Examination",
    "ETE": "End-Term Examination",
    "CA": "Continuous Assessment",
    "RP": "Re-appear Exam",
    "UMS": "University Management System",
    "LPU": "Lovely Professional University",
    "CSE": "Computer Science & Engineering",
    "ECE": "Electronics & Communication Engineering",
    "RMS": "Relationship Management System",
    "HOD": "Head of Department",
    "DSW": "Dean of Student Welfare",
    "COE": "Controller of Examinations",
    "DRC": "Department Result Committee",
    "GPA": "Grade Point Average",
    "SGPA": "Semester Grade Point Average",
    "CGPA": "Cumulative Grade Point Average",
    "OD": "On-Duty Leave",
    "MCQ": "Multiple Choice Question",
}


class AcronymExpander:
    """Expands domain-specific acronyms based on config/acronyms.yaml."""

    def __init__(self, config_path: Optional[str | Path] = None):
        self.acronyms: Dict[str, str] = {}
        self.departments: List[str] = []
        self._load_config(config_path)

    def _load_config(self, config_path: Optional[str | Path] = None) -> None:
        if config_path is None:
            # Default to <repo_root>/config/acronyms.yaml
            base_dir = Path(__file__).resolve().parent.parent.parent
            config_path = base_dir / "config" / "acronyms.yaml"
        else:
            config_path = Path(config_path)

        if config_path.is_file():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    self.acronyms = data.get("acronyms", {}) or {}
                    self.departments = data.get("department_names", []) or []
            except Exception as e:
                logger.warning("Could not read %s: %s. Using default acronyms.", config_path, e)
                self.acronyms = DEFAULT_ACRONYMS.copy()
        else:
            logger.info("Config file %s not found. Using default acronyms.", config_path)
            self.acronyms = DEFAULT_ACRONYMS.copy()

    def expand(self, text: str) -> Tuple[str, List[Tuple[str, str]]]:
        """Expand acronyms in text while preserving case.

        Returns:
            Tuple of (expanded_display_text, list_of_expanded_tuples)
            where list_of_expanded_tuples contains (original_word, expansion).
        """
        if not text:
            return text, []

        expanded_records: List[Tuple[str, str]] = []
        expanded_keys: Set[str] = set()

        result = text
        # Scan for potential unknown acronyms (2-5 uppercase letters)
        all_caps = re.findall(r"\b[A-Z]{2,5}\b", text)
        for cand in all_caps:
            if cand not in self.acronyms and not re.match(r"^[IVXLCDM]+$", cand):
                logger.debug("Observed unmapped acronym: %s", cand)

        for acronym, expansion in self.acronyms.items():
            # Whole-word, case-insensitive match
            pattern = re.compile(rf"\b({re.escape(acronym)})\b", re.IGNORECASE)

            def _repl(match: re.Match) -> str:
                matched_text = match.group(1)
                # Avoid double expansion if already followed by (Expansion)
                start, end = match.span()
                remainder = result[end:].lstrip()
                if remainder.startswith(f"({expansion})"):
                    return matched_text

                if acronym.upper() not in expanded_keys:
                    expanded_records.append((matched_text, expansion))
                    expanded_keys.add(acronym.upper())

                return f"{matched_text} ({expansion})"

            result = pattern.sub(_repl, result)

        return result, expanded_records
