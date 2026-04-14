"""Scaffold runner for the tt translation tool.

Provides setup_scaffold() which invokes the Ghostfolio scaffold setup script
via subprocess. Extracted from cli.py to make the step importable/testable.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def setup_scaffold(repo_root: Path, output_dir: Path) -> None:
    """Set up the Ghostfolio scaffold in output_dir.

    Calls helptools/setup_ghostfolio_scaffold_for_tt.py via subprocess,
    matching the behaviour that was previously inline in cli.py.

    Raises RuntimeError if the setup script is not found.
    """
    setup_script = repo_root / "helptools" / "setup_ghostfolio_scaffold_for_tt.py"
    if not setup_script.exists():
        raise RuntimeError(f"Setup script not found: {setup_script}")

    print(f"Setting up scaffold → {output_dir}")
    subprocess.run(
        [sys.executable, str(setup_script), "--output", str(output_dir)],
        check=True,
    )
