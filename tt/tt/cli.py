"""Translation tool CLI entry point."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tt.runner import setup_scaffold

REPO_ROOT = Path(__file__).parent.parent.parent.resolve()

# The default scaffold points at the ghostfolio_pytx project scaffold.
# Override with --scaffold to target a different project.
_DEFAULT_SCAFFOLD = Path(__file__).parent / "scaffold" / "ghostfolio_pytx"


def _load_config(scaffold_dir: Path) -> dict:
    config_file = scaffold_dir / "tt_config.json"
    if not config_file.exists():
        return {}
    return json.loads(config_file.read_text(encoding="utf-8"))


def cmd_translate(args: argparse.Namespace) -> int:
    scaffold_dir = Path(args.scaffold) if args.scaffold else _DEFAULT_SCAFFOLD
    config = _load_config(scaffold_dir)

    default_output = REPO_ROOT / config.get("default_output", "translations/output")
    example_dir = REPO_ROOT / config.get("example_dir", "translations/example")
    output_dir = Path(args.output) if args.output else default_output

    # Step 1: Set up the scaffold (copies example + support modules)
    print(f"Setting up scaffold -> {output_dir}")
    setup_scaffold(REPO_ROOT, output_dir, scaffold_dir, example_dir)

    # Step 2: Run the actual translation
    print(f"\nTranslating TypeScript to Python...")
    from tt.translator import run_translation
    run_translation(REPO_ROOT, output_dir, scaffold_dir)

    print(f"\nDone. Output at {output_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tt",
        description="TypeScript-to-Python translation tool",
    )
    sub = parser.add_subparsers(dest="command")

    p_translate = sub.add_parser("translate", help="Translate TypeScript to Python")
    p_translate.add_argument("-o", "--output", help="Output directory")
    p_translate.add_argument(
        "--scaffold",
        help="Scaffold directory containing tt_config.json and scaffold files",
        default=None,
    )

    args = parser.parse_args()
    if args.command == "translate":
        return cmd_translate(args)

    parser.print_help()
    return 0
