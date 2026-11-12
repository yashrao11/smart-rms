#!/usr/bin/env python3
"""Interactive / CLI test runner for Module 1 — Query Preprocessing."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.preprocessing import Preprocessor, RawQuery


def format_output(processed) -> str:
    data = {
        "original_text": processed.original_text,
        "normalized_text": processed.normalized_text,
        "display_text": processed.display_text,
        "processing_latency_ms": f"{processed.processing_latency_ms} ms",
        "entities": asdict(processed.entities),
    }
    return json.dumps(data, indent=2)


def main():
    preprocessor = Preprocessor()

    if len(sys.argv) > 1:
        query_text = " ".join(sys.argv[1:])
        print(f"\n--- Processing Query: '{query_text}' ---")
        try:
            result = preprocessor.process(query_text)
            print(format_output(result))
        except ValueError as err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)
        return

    print("=" * 60)
    print("SMART-RMS Query Preprocessing Module (Interactive Mode)")
    print("Type a university query or 'exit' / 'quit' to finish.")
    print("=" * 60)

    while True:
        try:
            raw_input_text = input("\nEnter query > ").strip()
            if not raw_input_text:
                continue
            if raw_input_text.lower() in {"exit", "quit", "q"}:
                print("Exiting.")
                break

            result = preprocessor.process(raw_input_text)
            print(format_output(result))
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break
        except ValueError as e:
            print(f"Validation Error: {e}")


if __name__ == "__main__":
    main()
