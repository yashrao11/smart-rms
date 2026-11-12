"""Main query preprocessing orchestration pipeline."""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from .acronym_expander import AcronymExpander
from .models import ProcessedQuery, RawQuery
from .ner import NamedEntityRecognizer
from .normalizer import clean_text, normalize
from .spell_corrector import SpellCorrector


class Preprocessor:
    """Orchestrates query normalization, spell checking, acronym expansion, and entity recognition."""

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        enable_spell_check: bool = True,
    ):
        self.acronym_expander = AcronymExpander(config_path=config_path)
        self.entity_recognizer = NamedEntityRecognizer(
            known_departments=self.acronym_expander.departments
        )
        self.enable_spell_check = enable_spell_check
        self.spell_corrector = SpellCorrector() if enable_spell_check else None

    def process(self, query: Union[str, RawQuery]) -> ProcessedQuery:
        """Process a raw query into a structured ProcessedQuery.

        Args:
            query: Either a raw query string or a RawQuery dataclass.

        Returns:
            ProcessedQuery with clean normalized text, display text, and extracted entities.

        Raises:
            ValueError: If the query is empty or invalid.
        """
        start_time = time.perf_counter()

        if isinstance(query, str):
            raw_query = RawQuery(text=query)
        elif isinstance(query, RawQuery):
            raw_query = query
        else:
            raise ValueError("Input must be a string or RawQuery instance")

        # 1. Basic cleaning and validation (enforces length & empty checks)
        cleaned = clean_text(raw_query.text)

        # 2. Spell correction (preserving proper nouns & acronyms)
        if self.spell_corrector:
            spell_checked = self.spell_corrector.correct(cleaned)
        else:
            spell_checked = cleaned

        # 3. Acronym expansion
        display_text, expanded_acronyms = self.acronym_expander.expand(spell_checked)

        # 4. Normalized lowercase text for search/retrieval
        normalized_text = normalize(display_text)

        # 5. Entity recognition
        entities = self.entity_recognizer.extract(
            text=display_text,
            acronyms_expanded=expanded_acronyms,
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        return ProcessedQuery(
            original_text=raw_query.text,
            normalized_text=normalized_text,
            display_text=display_text,
            entities=entities,
            processing_latency_ms=latency_ms,
            timestamp=datetime.now(timezone.utc),
        )
