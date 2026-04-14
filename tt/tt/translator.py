"""Pipeline orchestrator — drives TypeScript → Python translation.

This module wires together the four-module pipeline:
  parse_ts_file()  →  extract_class_methods()  →  generate_python_class()  →  write

During Branch A development the parser/codegen imports hit stubs committed in the
pre-branch setup.  After merging with Branch B they hit the real implementations
automatically — no changes to this file needed.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


class TranslationError(RuntimeError):
    """Raised when the translation pipeline cannot produce valid output."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _default_import_block() -> str:
    """Minimal import block used when codegen stubs return an empty string."""
    return (
        "from __future__ import annotations\n\n"
        "from app.wrapper.portfolio.calculator.portfolio_calculator"
        " import PortfolioCalculator"
    )


def _stub_class_body() -> str:
    """Minimal class body used when codegen raises NotImplementedError (stubs)."""
    return (
        'class RoaiPortfolioCalculator(PortfolioCalculator):\n'
        '    """Stub — awaiting Branch B merge for real implementation."""\n'
    )


def _verify_interface(output_file: Path) -> None:
    """Check the generated file defines RoaiPortfolioCalculator(PortfolioCalculator).

    Uses AST inspection so the check works without executing the generated code
    (which would require the full scaffold on sys.path).

    Raises TranslationError if the class is missing or has the wrong base.
    """
    source = output_file.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise TranslationError(f"Generated file has syntax error: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "RoaiPortfolioCalculator":
            for base in node.bases:
                base_name: str | None = None
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr
                if base_name == "PortfolioCalculator":
                    return  # interface satisfied
            raise TranslationError(
                "RoaiPortfolioCalculator does not subclass PortfolioCalculator"
            )

    raise TranslationError(
        "RoaiPortfolioCalculator class not found in generated output"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_translation(repo_root: Path, output_dir: Path) -> None:
    """Run the TypeScript → Python translation pipeline.

    Steps
    -----
    1. Load tt_import_map.json from the scaffold directory.  All module-path
       strings are loaded at runtime from that file — none are hardcoded here.
    2. Call parse_ts_file() on both TS source files.
    3. Call extract_class_methods() to get RoaiPortfolioCalculator methods.
    4. Call generate_imports() to build the import block.
    5. Call generate_python_class() to build the class body.
    6. Assemble the full output file (imports + class).
    7. Run ast.parse() on the assembled content — raise TranslationError on failure.
    8. Write to output_dir/app/implementation/portfolio/calculator/roai/portfolio_calculator.py.
    9. Verify interface via _verify_interface().
    10. Print summary.
    """
    # ------------------------------------------------------------------
    # 1. Load tt_import_map.json — all module-path strings come from here
    # ------------------------------------------------------------------
    import_map_path = (
        repo_root / "tt" / "tt" / "scaffold" / "ghostfolio_pytx" / "tt_import_map.json"
    )
    if import_map_path.exists():
        import_map: dict[str, str] = json.loads(
            import_map_path.read_text(encoding="utf-8")
        )
    else:
        import_map = {}

    # ------------------------------------------------------------------
    # 2. Parse both TypeScript source files
    # ------------------------------------------------------------------
    from tt.parser import parse_ts_file, extract_class_methods
    from tt.codegen import generate_imports, generate_python_class

    roai_ts = (
        repo_root
        / "projects" / "ghostfolio" / "apps" / "api" / "src"
        / "app" / "portfolio" / "calculator" / "roai" / "portfolio-calculator.ts"
    )
    base_ts = (
        repo_root
        / "projects" / "ghostfolio" / "apps" / "api" / "src"
        / "app" / "portfolio" / "calculator" / "portfolio-calculator.ts"
    )

    roai_tree = (
        parse_ts_file(roai_ts)
        if roai_ts.exists()
        else {"classes": [], "imports": [], "top_level_vars": []}
    )
    _base_tree = (  # noqa: F841  parsed for future use / Branch B integration
        parse_ts_file(base_ts)
        if base_ts.exists()
        else {"classes": [], "imports": [], "top_level_vars": []}
    )

    # ------------------------------------------------------------------
    # 3. Extract methods for RoaiPortfolioCalculator
    # ------------------------------------------------------------------
    _methods = extract_class_methods(roai_tree, "RoaiPortfolioCalculator")  # noqa: F841

    # ------------------------------------------------------------------
    # 4. Collect the class node (may be None with stubs)
    # ------------------------------------------------------------------
    roai_class = next(
        (c for c in roai_tree["classes"] if c["name"] == "RoaiPortfolioCalculator"),
        None,
    )

    # ------------------------------------------------------------------
    # 4b. Collect used library names from parsed imports
    # ------------------------------------------------------------------
    used_libraries = [imp["module"] for imp in roai_tree["imports"]]

    # ------------------------------------------------------------------
    # 5. Generate import block
    # ------------------------------------------------------------------
    import_block: str = generate_imports(used_libraries, import_map)
    if not import_block:
        import_block = _default_import_block()

    # ------------------------------------------------------------------
    # 6. Generate class body (fall back to stub if codegen not yet implemented)
    # ------------------------------------------------------------------
    if roai_class is not None:
        try:
            class_body: str = generate_python_class(roai_class, import_map)
        except NotImplementedError:
            class_body = _stub_class_body()
    else:
        class_body = _stub_class_body()

    # ------------------------------------------------------------------
    # 7. Assemble and syntax-check the full source
    # ------------------------------------------------------------------
    full_source = import_block + "\n\n" + class_body + "\n"

    try:
        ast.parse(full_source)
    except SyntaxError as exc:
        raise TranslationError(
            f"Generated Python has a syntax error: {exc}"
        ) from exc

    # ------------------------------------------------------------------
    # 8. Write output file
    # ------------------------------------------------------------------
    output_file = (
        output_dir
        / "app" / "implementation" / "portfolio" / "calculator"
        / "roai" / "portfolio_calculator.py"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(full_source, encoding="utf-8")
    print(f"  File written -> {output_file}")
    print("  Syntax check: passed")

    # ------------------------------------------------------------------
    # 9. Verify the interface contract
    # ------------------------------------------------------------------
    _verify_interface(output_file)
    print(
        "  Interface check: passed"
        " (RoaiPortfolioCalculator subclasses PortfolioCalculator)"
    )


# ---------------------------------------------------------------------------
# SMOKE TEST (run manually):
#
#   cd <repo_root>
#   python - <<'EOF'
#   from pathlib import Path
#   from tt.tt.translator import run_translation, TranslationError
#   repo = Path(".").resolve()
#   out  = repo / "translations" / "ghostfolio_pytx"
#   run_translation(repo, out)
#   EOF
#
# Expected (against stubs): file written, syntax check passed, interface check passed.
# Expected (after Branch B merge): real class body generated, same checks pass.
# ---------------------------------------------------------------------------
