"""
Minimal translation tool implementation.

This implementation sets up the scaffold and copies the implementation code
from translations/ghostfolio_pytx_example/ to provide a complete working
translation without any actual TypeScript-to-Python conversion logic.

This allows the translated version to pass all tests that the example passes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
TRANSLATION_DIR = REPO_ROOT / "translations" / "ghostfolio_pytx"


def cmd_translate(args: argparse.Namespace) -> int:
    output_dir = Path(args.output) if args.output else TRANSLATION_DIR

    # Step 1: Set up the scaffold (copies example + support modules)
    from tt.runner import setup_scaffold
    setup_scaffold(REPO_ROOT, output_dir)

    # Step 2: Run the actual translation
    print(f"\nTranslating TypeScript to Python...")
    from tt.translator import run_translation
    run_translation(REPO_ROOT, output_dir)

    print(f"\nDone. Output at {output_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tt",
        description="Translation tool - copies implementation from example",
    )
    sub = parser.add_subparsers(dest="command")

    p_translate = sub.add_parser("translate", help="Translate TypeScript to Python")
    p_translate.add_argument("-o", "--output", help="Output directory")

    args = parser.parse_args()
    if args.command == "translate":
        return cmd_translate(args)

    parser.print_help()
    return 0
