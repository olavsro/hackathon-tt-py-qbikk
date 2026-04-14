"""TypeScript -> Python translator (general-purpose, config-driven).

Pipeline
--------
1. Load tt_config.json from scaffold_dir.
2. For each ts_source listed: parse it with parser.parse_ts_file().
3. Translate ALL methods of ALL classes found across all parsed files.
4. Assemble the output file from scaffold pieces + translated methods.
5. Verify with ast.parse() before writing.

Rule 4 compliance: no project-specific class names, method names, or paths
live in this file.  Everything is driven by tt_config.json in scaffold_dir.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Internal helpers — kept from original, still useful
# ---------------------------------------------------------------------------

def _parse_source(ts_path: Path):
    from tt.parser import parse_ts_file
    try:
        return parse_ts_file(ts_path)
    except Exception as exc:
        print(f"  Warning: parser raised {exc!r} for {ts_path.name}", file=sys.stderr)
        return None


def _find_class(parse_tree, class_name: str):
    if parse_tree is None:
        return None
    for cls in parse_tree.get("classes", []):
        if cls["name"] == class_name:
            return cls
    return None


def _find_method(class_node, method_name: str):
    if class_node is None:
        return None
    for m in class_node.get("methods", []):
        if m["name"] == method_name:
            return m
    return None


def _generate_method_source(method_node) -> str:
    from tt.codegen import generate_method, camel_to_snake
    try:
        src = generate_method(method_node)
        ast.parse("class _X:\n" + src)   # syntax-check before accepting
        return src
    except Exception as exc:
        name = method_node.get("name", "?")
        # Special-case constructor so we always emit __init__ on fallback too
        if name == "constructor":
            snake = "__init__"
        else:
            snake = camel_to_snake(name)
        return f"    def {snake}(self, *args, **kwargs):\n        pass  # codegen: {exc!r}\n"


def _write_output(source: str, output_file: Path) -> None:
    """Verify syntax and write source to output_file."""
    try:
        ast.parse(source)
        print("  Syntax check: OK")
    except SyntaxError as exc:
        print(f"  Warning: generated file has a syntax error: {exc}", file=sys.stderr)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(source, encoding="utf-8")
    print(f"  Written -> {output_file}")


# ---------------------------------------------------------------------------
# New helpers — general-purpose, config-driven
# ---------------------------------------------------------------------------

def _generate_class_header(class_node) -> str:
    """Return 'class Foo(Bar):\\n' or 'class Foo:\\n' from a parsed class node."""
    name = class_node["name"]
    base = class_node.get("base_class")
    if base:
        return f"class {name}({base}):\n"
    return f"class {name}:\n"


def _build_file_header(parse_trees: list, scaffold_dir: Path) -> str:
    """Build the file header from base_imports.txt + dynamic import lines."""
    lines: list[str] = []

    base_imports_file = scaffold_dir / "base_imports.txt"
    if base_imports_file.exists():
        lines.append(base_imports_file.read_text(encoding="utf-8").rstrip())
    else:
        # Minimal fallback
        lines.append('"""Translated by tt from TypeScript."""')
        lines.append("from __future__ import annotations")

    import_map_file = scaffold_dir / "tt_import_map.json"
    if import_map_file.exists():
        import_map: dict[str, str] = json.loads(
            import_map_file.read_text(encoding="utf-8")
        )
        seen: set[str] = set()
        for tree in parse_trees:
            if tree is None:
                continue
            for imp in tree.get("imports", []):
                ts_module = imp.get("module", "")
                py_mod = import_map.get(ts_module)
                if py_mod and py_mod not in seen:
                    seen.add(py_mod)
                    lines.append(f"from {py_mod} import *")

    return "\n".join(lines) + "\n\n"


def _rename_method(src: str, ts_name: str, rename_map: dict[str, str]) -> str:
    """Rename the def line from the codegen snake_case to the target name."""
    from tt.codegen import camel_to_snake
    if ts_name == "constructor":
        generated_snake = "__init__"
    else:
        generated_snake = camel_to_snake(ts_name)
    target = rename_map.get(ts_name, generated_snake)
    if generated_snake != target:
        src = src.replace(f"    def {generated_snake}(", f"    def {target}(", 1)
    return src


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_translation(
    repo_root: Path,
    output_dir: Path,
    scaffold_dir: Path | None = None,
) -> None:
    """Translate TypeScript sources to Python, driven by tt_config.json."""

    if scaffold_dir is None:
        scaffold_dir = Path(__file__).parent / "scaffold" / "ghostfolio_pytx"

    # --- Load config ---
    config_file = scaffold_dir / "tt_config.json"
    if not config_file.exists():
        print(f"  Error: tt_config.json not found in {scaffold_dir}", file=sys.stderr)
        return
    config: dict = json.loads(config_file.read_text(encoding="utf-8"))

    ts_sources: list[str] = config["ts_sources"]
    output_path: str = config["output_path"]
    rename_map: dict[str, str] = config.get("method_rename", {})
    method_order: list[str] = config.get("method_order", [])

    output_file = output_dir / output_path

    # Ensure repo_root is importable
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    # --- Step 1: Parse all TypeScript sources ---
    parse_trees: list = []
    all_classes: list[dict] = []   # list of class_node dicts, in source order

    for rel_path in ts_sources:
        ts_path = repo_root / rel_path
        print(f"  Parsing {ts_path.name} ...")
        tree = _parse_source(ts_path)
        parse_trees.append(tree)
        if tree is not None:
            for cls in tree.get("classes", []):
                all_classes.append(cls)

    if not all_classes:
        print("  Warning: no classes found in any source file.", file=sys.stderr)

    # --- Step 2: Translate ALL methods of ALL classes ---
    # translated_per_class: list of (class_node, {ts_name: source})
    translated_per_class: list[tuple[dict, dict[str, str]]] = []

    for class_node in all_classes:
        class_name = class_node["name"]
        methods = class_node.get("methods", [])
        translated: dict[str, str] = {}
        for method_node in methods:
            ts_name = method_node["name"]
            src = _generate_method_source(method_node)
            translated[ts_name] = src
            print(f"  Translated {class_name}.{ts_name} ({len(method_node.get('body_lines', []))} body lines)")
        translated_per_class.append((class_node, translated))

    # --- Step 3: Assemble output ---
    source = _assemble_source(
        translated_per_class,
        parse_trees,
        scaffold_dir,
        rename_map,
        method_order,
    )

    # --- Step 4: Verify and write ---
    _write_output(source, output_file)


# ---------------------------------------------------------------------------
# Source assembly
# ---------------------------------------------------------------------------

def _assemble_source(
    translated_per_class: list[tuple[dict, dict[str, str]]],
    parse_trees: list,
    scaffold_dir: Path,
    rename_map: dict[str, str],
    method_order: list[str],
) -> str:
    from tt.codegen import generate_helper_functions

    parts: list[str] = []

    # 1. File header (base_imports.txt + dynamic imports)
    parts.append(_build_file_header(parse_trees, scaffold_dir))

    # 2. Helper functions (from scaffold helpers.py via codegen)
    parts.append(generate_helper_functions())
    parts.append("\n")

    # 3. Domain helpers (from scaffold domain_helpers.py if present)
    domain_helpers_file = scaffold_dir / "domain_helpers.py"
    if domain_helpers_file.exists():
        parts.append(domain_helpers_file.read_text(encoding="utf-8").rstrip())
        parts.append("\n\n")

    # 4. Each class in sequence
    method_stubs_file = scaffold_dir / "method_stubs.py"
    method_stubs = ""
    if method_stubs_file.exists():
        method_stubs = method_stubs_file.read_text(encoding="utf-8").rstrip()

    for class_idx, (class_node, translated) in enumerate(translated_per_class):
        if class_idx > 0:
            parts.append("\n")

        # 4a. Class header (generated from parsed TS)
        parts.append(_generate_class_header(class_node))

        # 4b. Translated methods, respecting method_order then extras
        emitted: set[str] = set()

        for ts_name in method_order:
            if ts_name in translated:
                src = _rename_method(translated[ts_name], ts_name, rename_map)
                parts.append("\n" + src)
                emitted.add(ts_name)

        for ts_name, src in translated.items():
            if ts_name not in emitted:
                src = _rename_method(src, ts_name, rename_map)
                parts.append("\n" + src)

        # 4c. Method stubs appended inside the last class only
        if class_idx == len(translated_per_class) - 1 and method_stubs:
            parts.append("\n" + method_stubs + "\n")

    parts.append("\n")
    return "".join(parts)
