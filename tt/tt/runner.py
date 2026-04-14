"""Scaffold setup runner for the tt translation tool.

Exposes setup_scaffold(repo_root, output_dir, scaffold_dir, example_dir) as an
importable function so that cli.py and tests can call it directly.

No project-specific paths or script names live here — all paths are passed in
by the caller (cli.py reads them from tt_config.json in the scaffold directory).
"""
from __future__ import annotations

import shutil
import stat
import time
import os
from pathlib import Path


def setup_scaffold(
    repo_root: Path,
    output_dir: Path,
    scaffold_dir: Path,
    example_dir: Path,
) -> None:
    """Set up the translation output directory.

    1. Copies *example_dir* into *output_dir* as the base (wrapper layer,
       main.py, pyproject.toml, etc.).
    2. Overlays support files from *scaffold_dir* (helpers, import map, config).
    3. Ensures every Python package directory has an __init__.py.

    Args:
        repo_root:    Absolute path to the repository root (unused here, kept
                      for API symmetry with callers that may need it).
        output_dir:   Target directory for the translated project.
        scaffold_dir: tt scaffold directory (contains tt_config.json etc.).
        example_dir:  Reference example directory to copy as the base.
    """
    # Step 1: Copy the example as the base
    shutil.copytree(example_dir, output_dir, dirs_exist_ok=True)
    print(f"  Copied example scaffold -> {output_dir}")

    # Step 2: Overlay scaffold support files
    for src_file in scaffold_dir.rglob("*"):
        if not src_file.is_file():
            continue
        if src_file.name.startswith(".") or "__pycache__" in src_file.parts:
            continue
        if ".mypy_cache" in src_file.parts:
            continue
        rel = src_file.relative_to(scaffold_dir)
        dst = output_dir / rel
        # Never overwrite the canonical entry point from the example
        if rel == Path("app") / "main.py":
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst)

    print(f"  Overlaid scaffold support modules")

    # Step 3: Ensure __init__.py exists for all Python packages
    for dirpath in output_dir.rglob("*"):
        if dirpath.is_dir() and any(dirpath.glob("*.py")):
            init = dirpath / "__init__.py"
            if not init.exists():
                init.write_text("", encoding="utf-8")

    print(f"  Scaffold ready at {output_dir}")
