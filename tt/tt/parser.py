"""TypeScript parser for the Ghostfolio calculator sources.

Pattern inventory from Branch B-1:
- import { X, Y } from 'module'
- export abstract class Foo { ... }
- export class Foo extends Bar { ... }
- private/protected/public methodName(params: Type): ReturnType { body }
- private fieldName: Type;
- private static readonly CONST = value;
- const x: Type = new Big(0);
- nested braces, if/else, for-of, optional chaining, nullish coalescing,
  arrow functions, template literals, and object literals are preserved as raw
  body lines; parser logic only needs to find the matching method brace.

The implementation intentionally stays small: it uses regex for member shape
classification and bracket-depth tracking for statement and body boundaries.
"""
from __future__ import annotations

import re
from pathlib import Path

from contracts.parse_tree_schema import (
    ClassNode,
    ImportNode,
    MethodNode,
    ParseTree,
    ParamNode,
    PropertyNode,
)


_IMPORT_RE = re.compile(
    r"^import\s+\{\s*(?P<symbols>[^}]+?)\s*\}\s+from\s+['\"](?P<module>[^'\"]+)['\"]\s*;?$"
)
_CLASS_RE = re.compile(
    r"^export\s+(?P<abstract>abstract\s+)?class\s+"
    r"(?P<name>[A-Za-z_$][\w$]*)"
    r"(?:\s+extends\s+(?P<base>[A-Za-z_$][\w$]*))?\s*\{?$"
)
_METHOD_START_RE = re.compile(
    r"^(?:(?P<visibility>public|protected|private)\s+)?"
    r"(?P<static>static\s+)?"
    r"(?P<abstract>abstract\s+)?"
    r"(?:(?P<async>async)\s+)?"
    r"(?P<name>constructor|[A-Za-z_$][\w$]*)"
)
_PROPERTY_START_RE = re.compile(
    r"^(?:(?P<visibility>public|protected|private)\s+)?"
    r"(?P<static>static\s+)?"
    r"(?P<readonly>readonly\s+)?"
    r"(?P<name>[A-Za-z_$][\w$]*)"
)
_TOP_LEVEL_CONST_RE = re.compile(
    r"^(?:export\s+)?const\s+(?P<name>[A-Za-z_$][\w$]*)"
    r"(?:\s*:\s*(?P<ts_type>[^=;]+))?"
    r"\s*=\s*(?P<initializer>.+);$"
)


# Pattern inventory notes:
# - class headers are detected on a single line.
# - class members may span multiple lines, but the member opener still begins on
#   the first line of the declaration.
# - method body extraction is brace-aware; method bodies are returned verbatim
#   as `body_lines` without translation or comment rewriting.
# - property declarations are consumed until their terminating semicolon.
# - top-level `const` statements are collected as simple data rows.


def parse_ts_file(path: Path) -> ParseTree:
    """Parse a TypeScript source file into a minimal parse tree."""

    source = path.read_text(encoding="utf-8")
    clean_source = _strip_comments(source)
    scan_source = _strip_templates(clean_source)
    raw_lines = source.splitlines()
    scan_lines = scan_source.splitlines()

    imports = _scan_imports(raw_lines, scan_lines)
    classes = _scan_classes(raw_lines, scan_lines)
    top_level_vars = _scan_top_level_consts(raw_lines, scan_lines)

    return {
        "classes": classes,
        "imports": imports,
        "top_level_vars": top_level_vars,
    }


def _scan_imports(raw_lines: list[str], scan_lines: list[str]) -> list[ImportNode]:
    """Collect all top-level import nodes from scan_lines."""
    imports: list[ImportNode] = []
    i = 0
    while i < len(raw_lines):
        clean_line = scan_lines[i].strip()
        if not clean_line:
            i += 1
            continue
        if clean_line.startswith("import "):
            statement_lines, next_index = _collect_statement_lines(scan_lines, i)
            statement = _normalize_lines(statement_lines)
            import_node = _parse_import_statement(statement)
            if import_node is not None:
                imports.append(import_node)
            i = next_index
        else:
            i += 1
    return imports


def _scan_classes(raw_lines: list[str], scan_lines: list[str]) -> list[ClassNode]:
    """Collect all top-level exported class nodes from scan_lines."""
    classes: list[ClassNode] = []
    i = 0
    while i < len(raw_lines):
        clean_line = scan_lines[i].strip()
        if not clean_line:
            i += 1
            continue
        class_match = _CLASS_RE.match(clean_line)
        if class_match and clean_line.startswith("export "):
            class_start = i
            class_end, _ = _find_matching_brace(
                scan_lines, class_start, _find_open_brace(scan_lines[class_start])
            )
            class_body_raw = raw_lines[class_start + 1 : class_end]
            class_body_clean = scan_lines[class_start + 1 : class_end]
            classes.append(_parse_class(
                raw_lines[class_start],
                class_match,
                class_body_raw,
                class_body_clean,
            ))
            i = class_end + 1
        else:
            i += 1
    return classes


def _scan_top_level_consts(raw_lines: list[str], scan_lines: list[str]) -> list[dict]:
    """Collect all top-level const variable nodes from scan_lines."""
    top_level_vars: list[dict] = []
    i = 0
    while i < len(raw_lines):
        clean_line = scan_lines[i].strip()
        if not clean_line:
            i += 1
            continue
        if clean_line.startswith("const "):
            statement_lines, next_index = _collect_statement_lines(scan_lines, i)
            statement = _normalize_lines(statement_lines)
            top_level_var = _parse_top_level_const(statement)
            if top_level_var is not None:
                top_level_vars.append(top_level_var)
            i = next_index
        else:
            i += 1
    return top_level_vars


def extract_class_methods(parse_tree: ParseTree, class_name: str) -> list[MethodNode]:
    """Return the methods for a parsed class, or an empty list if missing."""

    for class_node in parse_tree["classes"]:
        if class_node["name"] == class_name:
            return class_node["methods"]
    return []


def _parse_class(
    class_header_line: str,
    class_match: re.Match[str],
    body_raw_lines: list[str],
    body_clean_lines: list[str],
) -> ClassNode:
    methods: list[MethodNode] = []
    properties: list[PropertyNode] = []

    i = 0
    while i < len(body_raw_lines):
        clean_line = body_clean_lines[i].strip()

        if not clean_line:
            i += 1
            continue

        if body_raw_lines[i].strip().startswith("@"):
            i += 1
            continue

        next_i = _try_parse_method(
            body_raw_lines, body_clean_lines, i, clean_line, methods
        )
        if next_i is not None:
            i = next_i
            continue

        next_i = _try_parse_property(
            body_raw_lines, body_clean_lines, i, clean_line, properties
        )
        if next_i is not None:
            i = next_i
            continue

        i += 1

    return {
        "name": class_match.group("name"),
        "base_class": class_match.group("base"),
        "methods": methods,
        "properties": properties,
    }


def _try_parse_method(
    body_raw_lines: list[str],
    body_clean_lines: list[str],
    i: int,
    clean_line: str,
    methods: list[MethodNode],
) -> int | None:
    """Try to parse a method at position i. Appends to methods and returns next index, or None."""
    if not _looks_like_method_start(clean_line):
        return None

    try:
        end_kind, end_line, end_col = _find_member_terminator(
            body_clean_lines, i, member_kind="method"
        )
    except ValueError:
        # Could not find terminator — skip this line and continue
        return i + 1

    signature_lines = body_raw_lines[i : end_line + 1][:]
    signature_lines[-1] = signature_lines[-1][:end_col]

    try:
        methods.append(_parse_method(
            signature_lines,
            body_raw_lines,
            body_clean_lines,
            i,
            end_line,
            end_col,
            end_kind,
        ))
    except ValueError:
        # Could not parse signature — skip to after the body if possible
        if end_kind == "body":
            try:
                close_line, _ = _find_matching_brace(body_clean_lines, end_line, end_col)
                return close_line + 1
            except ValueError:
                return i + 1
        return end_line + 1

    if end_kind == "body":
        try:
            close_line, _ = _find_matching_brace(body_clean_lines, end_line, end_col)
            return close_line + 1
        except ValueError:
            return i + 1
    return end_line + 1


def _try_parse_property(
    body_raw_lines: list[str],
    body_clean_lines: list[str],
    i: int,
    clean_line: str,
    properties: list[PropertyNode],
) -> int | None:
    """Try to parse a property at position i. Appends to properties and returns next index, or None."""
    if not _looks_like_property_start(clean_line):
        return None

    try:
        end_kind, end_line, end_col = _find_member_terminator(
            body_clean_lines, i, member_kind="property"
        )
    except ValueError:
        return i + 1

    signature_lines = body_raw_lines[i : end_line + 1][:]
    signature_lines[-1] = signature_lines[-1][:end_col]
    try:
        properties.append(_parse_property(signature_lines))
    except ValueError:
        pass
    return end_line + 1


def _parse_method(
    signature_lines: list[str],
    body_raw_lines: list[str],
    body_clean_lines: list[str],
    start_index: int,
    end_line: int,
    end_col: int,
    end_kind: str,
) -> MethodNode:
    name, visibility, params, return_type = _parse_method_signature(
        signature_lines, end_kind
    )
    body_lines = _extract_method_body(
        body_raw_lines, body_clean_lines, end_line, end_col, end_kind
    )
    return {
        "name": name,
        "visibility": visibility,
        "params": params,
        "return_type": return_type,
        "body_lines": body_lines,
    }


def _parse_method_signature(
    signature_lines: list[str],
    end_kind: str,
) -> tuple[str, str, list[ParamNode], str]:
    """Parse method signature lines and return (name, visibility, params, return_type)."""
    signature_text = _normalize_lines(signature_lines)
    if end_kind == "body":
        signature_text = signature_text.rstrip("{").strip()
    else:
        signature_text = signature_text.rstrip(";").strip()

    open_paren_index = signature_text.find("(")
    if open_paren_index < 0:
        raise ValueError(f"Method signature missing parameter list: {signature_text}")

    prefix = signature_text[:open_paren_index].strip()
    params_text, tail_text = _extract_balanced_segment(
        signature_text, open_paren_index, "(", ")"
    )
    params = _parse_params(params_text)

    prefix_match = _METHOD_START_RE.match(prefix)
    if prefix_match is None:
        raise ValueError(f"Could not parse method signature: {signature_text}")

    visibility = prefix_match.group("visibility") or ""
    name = prefix_match.group("name")
    return_type = _extract_return_type(tail_text, end_kind)
    return name, visibility, params, return_type


def _extract_return_type(tail_text: str, end_kind: str) -> str:
    """Extract return type string from the tail text after the parameter list."""
    tail_text = tail_text.strip()
    if not tail_text.startswith(":"):
        return ""
    return_type = tail_text[1:].strip()
    if end_kind == "body" and return_type.endswith("{"):
        return_type = return_type[:-1].strip()
    elif end_kind != "body" and return_type.endswith(";"):
        return_type = return_type[:-1].strip()
    return return_type


def _extract_method_body(
    body_raw_lines: list[str],
    body_clean_lines: list[str],
    end_line: int,
    end_col: int,
    end_kind: str,
) -> list[str]:
    """Extract method body lines between the opening and closing brace."""
    body_lines: list[str] = []
    if end_kind != "body":
        return body_lines

    open_line = end_line
    close_line, close_col = _find_matching_brace(body_clean_lines, open_line, end_col)
    if open_line == close_line:
        inner = body_raw_lines[open_line][end_col + 1 : close_col]
        if inner.strip():
            body_lines.append(inner)
    else:
        first_tail = body_raw_lines[open_line][end_col + 1 :]
        if first_tail.strip():
            body_lines.append(first_tail)
        body_lines.extend(body_raw_lines[open_line + 1 : close_line])
        last_head = body_raw_lines[close_line][:close_col]
        if last_head.strip():
            body_lines.append(last_head)
    return body_lines


def _parse_property(signature_lines: list[str]) -> PropertyNode:
    signature_text = _normalize_lines(signature_lines).rstrip(";").strip()
    eq_split = _split_top_level_once(signature_text, "=")
    left = signature_text
    right = ""
    if eq_split is not None:
        left, right = eq_split[0].strip(), eq_split[1].strip()

    colon_split = _split_top_level_once(left, ":")
    if colon_split is not None:
        head, ts_type = colon_split[0].strip(), colon_split[1].strip()
    else:
        head, ts_type = left.strip(), ""

    prefix_match = _PROPERTY_START_RE.match(head)
    if prefix_match is None:
        raise ValueError(f"Could not parse property signature: {signature_text}")

    return {
        "name": prefix_match.group("name"),
        "ts_type": ts_type,
        "visibility": prefix_match.group("visibility") or "",
        "is_static": bool(prefix_match.group("static")),
    }


def _parse_import_statement(statement: str) -> ImportNode | None:
    match = _IMPORT_RE.match(statement)
    if match is None:
        return None

    symbols = [
        symbol.strip()
        for symbol in match.group("symbols").split(",")
        if symbol.strip()
    ]
    return {
        "symbols": symbols,
        "module": match.group("module"),
    }


def _parse_top_level_const(statement: str) -> dict | None:
    match = _TOP_LEVEL_CONST_RE.match(statement)
    if match is None:
        return None
    return {
        "name": match.group("name"),
        "ts_type": (match.group("ts_type") or "").strip(),
        "initializer": match.group("initializer").strip(),
    }


def _parse_params(params_text: str) -> list[ParamNode]:
    inner = params_text.strip()
    if inner.startswith("(") and inner.endswith(")"):
        inner = inner[1:-1]
    if not inner.strip():
        return []

    params: list[ParamNode] = []
    for segment in _split_top_level(inner, ","):
        segment = segment.strip()
        if not segment:
            continue

        default_split = _split_top_level_once(segment, "=")
        if default_split is not None:
            segment = default_split[0].strip()

        colon_split = _split_top_level_once(segment, ":")
        if colon_split is not None:
            name, ts_type = colon_split[0].strip(), colon_split[1].strip()
        else:
            name, ts_type = segment.strip(), ""

        params.append({"name": name, "ts_type": ts_type})

    return params


def _looks_like_method_start(line: str) -> bool:
    if "(" not in line:
        return False

    if "=" in line:
        eq_index = line.find("=")
        paren_index = line.find("(")
        if eq_index < paren_index:
            return False

    return bool(_METHOD_START_RE.match(line))


def _looks_like_property_start(line: str) -> bool:
    if "(" in line and "=" not in line:
        return False

    head = _split_head_before_terminator(line)
    if head is None:
        return False

    return bool(_PROPERTY_START_RE.match(head))


def _split_head_before_terminator(line: str) -> str | None:
    for separator in (":", "=", ";"):
        split = _split_top_level_once(line, separator)
        if split is not None:
            return split[0].strip()
    return line.strip() or None


def _find_member_terminator(
    lines: list[str],
    start_index: int,
    member_kind: str,
) -> tuple[str, int, int]:
    paren_depth = 0
    bracket_depth = 0
    after_params = False
    saw_colon = False
    return_type_started = False
    return_brace_depth = 0
    in_string: str | None = None
    escape = False

    for line_index in range(start_index, len(lines)):
        line = lines[line_index]
        for col, ch in enumerate(line):
            result = _process_terminator_char(
                ch, col, line_index, member_kind,
                paren_depth, bracket_depth,
                after_params, saw_colon, return_type_started, return_brace_depth,
                in_string, escape,
            )
            (
                paren_depth, bracket_depth,
                after_params, saw_colon, return_type_started, return_brace_depth,
                in_string, escape, terminal,
            ) = result
            if terminal is not None:
                return terminal

    raise ValueError("Could not find member terminator")


def _process_terminator_char(
    ch: str,
    col: int,
    line_index: int,
    member_kind: str,
    paren_depth: int,
    bracket_depth: int,
    after_params: bool,
    saw_colon: bool,
    return_type_started: bool,
    return_brace_depth: int,
    in_string: str | None,
    escape: bool,
) -> tuple:
    """Process a single character for _find_member_terminator state machine.

    Returns updated state tuple ending with terminal (kind, line, col) or None.
    """
    terminal = None

    if in_string is not None:
        if escape:
            escape = False
            return (paren_depth, bracket_depth, after_params, saw_colon,
                    return_type_started, return_brace_depth, in_string, escape, terminal)
        if ch == "\\":
            escape = True
            return (paren_depth, bracket_depth, after_params, saw_colon,
                    return_type_started, return_brace_depth, in_string, escape, terminal)
        if ch == in_string:
            in_string = None
        return (paren_depth, bracket_depth, after_params, saw_colon,
                return_type_started, return_brace_depth, in_string, escape, terminal)

    if ch in ("'", '"', "`"):
        in_string = ch
        return (paren_depth, bracket_depth, after_params, saw_colon,
                return_type_started, return_brace_depth, in_string, escape, terminal)

    paren_depth, bracket_depth, after_params = _update_bracket_depths(
        ch, paren_depth, bracket_depth, after_params
    )

    if paren_depth > 0 or bracket_depth > 0:
        return (paren_depth, bracket_depth, after_params, saw_colon,
                return_type_started, return_brace_depth, in_string, escape, terminal)

    if member_kind == "method":
        saw_colon, return_type_started, return_brace_depth, terminal = (
            _advance_method_terminator_state(
                ch, col, line_index,
                after_params, saw_colon, return_type_started, return_brace_depth,
            )
        )
    else:
        if ch == ";":
            terminal = ("statement", line_index, col)

    return (paren_depth, bracket_depth, after_params, saw_colon,
            return_type_started, return_brace_depth, in_string, escape, terminal)


def _update_bracket_depths(
    ch: str,
    paren_depth: int,
    bracket_depth: int,
    after_params: bool,
) -> tuple[int, int, bool]:
    """Update paren/bracket depths and after_params flag for a single character."""
    if ch == "(":
        paren_depth += 1
    elif ch == ")" and paren_depth > 0:
        paren_depth -= 1
        if paren_depth == 0:
            after_params = True
    elif ch == "[":
        bracket_depth += 1
    elif ch == "]" and bracket_depth > 0:
        bracket_depth -= 1
    return paren_depth, bracket_depth, after_params


def _body_or_abstract(ch: str, col: int, line_index: int) -> tuple | None:
    """Return terminal for body-open or abstract-semicolon, else None."""
    if ch == "{":
        return ("body", line_index, col)
    if ch == ";":
        return ("abstract", line_index, col)
    return None


def _advance_method_terminator_state(
    ch: str,
    col: int,
    line_index: int,
    after_params: bool,
    saw_colon: bool,
    return_type_started: bool,
    return_brace_depth: int,
) -> tuple[bool, bool, int, tuple | None]:
    """Advance the method-specific state machine for one character."""
    terminal = None
    if not after_params:
        return saw_colon, return_type_started, return_brace_depth, terminal
    if not saw_colon and not return_type_started:
        if not ch.isspace() and ch not in (")", "(", "[", "]"):
            if ch == ":":
                saw_colon = True
            else:
                terminal = _body_or_abstract(ch, col, line_index)
                if terminal is None:
                    return_type_started = True
        return saw_colon, return_type_started, return_brace_depth, terminal
    if saw_colon:
        if not return_type_started:
            if not ch.isspace():
                return_type_started = True
                if ch == "{":
                    return_brace_depth = 1
                elif ch == ";":
                    terminal = ("abstract", line_index, col)
            return saw_colon, return_type_started, return_brace_depth, terminal
        if return_brace_depth > 0:
            if ch == "{":
                return_brace_depth += 1
            elif ch == "}":
                return_brace_depth -= 1
            return saw_colon, return_type_started, return_brace_depth, terminal
        if not ch.isspace():
            terminal = _body_or_abstract(ch, col, line_index)
    return saw_colon, return_type_started, return_brace_depth, terminal


def _find_matching_brace(
    lines: list[str],
    start_line: int,
    start_col: int,
) -> tuple[int, int]:
    depth = 1
    in_string: str | None = None
    escape = False

    for line_index in range(start_line, len(lines)):
        line = lines[line_index]
        col_start = start_col + 1 if line_index == start_line else 0
        for col in range(col_start, len(line)):
            ch = line[col]

            if in_string is not None:
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == in_string:
                    in_string = None
                continue

            if ch in ("'", '"', "`"):
                in_string = ch
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return line_index, col

    raise ValueError("Could not find matching brace")


def _extract_balanced_segment(
    text: str,
    open_index: int,
    open_char: str,
    close_char: str,
) -> tuple[str, str]:
    depth = 0
    in_string: str | None = None
    escape = False

    for index in range(open_index, len(text)):
        ch = text[index]

        if in_string is not None:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == in_string:
                in_string = None
            continue

        if ch in ("'", '"', "`"):
            in_string = ch
            continue

        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return text[open_index : index + 1], text[index + 1 :]

    raise ValueError(f"Unbalanced segment starting at {open_index}")


def _collect_statement_lines(lines: list[str], start_index: int) -> tuple[list[str], int]:
    collected: list[str] = []
    in_string: str | None = None
    escape = False

    for line_index in range(start_index, len(lines)):
        line = lines[line_index]
        collected.append(line)
        for ch in line:
            if in_string is not None:
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == in_string:
                    in_string = None
                continue

            if ch in ("'", '"', "`"):
                in_string = ch
                continue

            if ch == ";":
                return collected, line_index + 1

    return collected, len(lines)


def _split_top_level(text: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depths = [0, 0, 0]  # paren, bracket, brace
    in_string: str | None = None
    escape = False

    for ch in text:
        in_string, escape, consumed = _advance_string_state(ch, in_string, escape)
        if consumed:
            current.append(ch)
            continue

        if ch in ("'", '"', "`"):
            in_string = ch
            current.append(ch)
            continue

        depths = _update_nesting_depths(ch, depths)

        if ch == delimiter and depths[0] == 0 and depths[1] == 0 and depths[2] == 0:
            parts.append("".join(current))
            current = []
            continue

        current.append(ch)

    parts.append("".join(current))
    return parts


def _split_top_level_once(text: str, delimiter: str) -> tuple[str, str] | None:
    depths = [0, 0, 0]  # paren, bracket, brace
    in_string: str | None = None
    escape = False

    for index, ch in enumerate(text):
        in_string, escape, consumed = _advance_string_state(ch, in_string, escape)
        if consumed:
            continue

        if ch in ("'", '"', "`"):
            in_string = ch
            continue

        depths = _update_nesting_depths(ch, depths)

        if ch == delimiter and depths[0] == 0 and depths[1] == 0 and depths[2] == 0:
            return text[:index], text[index + 1 :]

    return None


def _advance_string_state(
    ch: str,
    in_string: str | None,
    escape: bool,
) -> tuple[str | None, bool, bool]:
    """Advance string-literal tracking for one character.

    Returns (in_string, escape, consumed) where consumed=True means the character
    was part of a string literal and should not be treated as syntax.
    """
    if in_string is None:
        return in_string, escape, False
    if escape:
        return in_string, False, True
    if ch == "\\":
        return in_string, True, True
    if ch == in_string:
        return None, False, True
    return in_string, False, True


def _update_nesting_depths(ch: str, depths: list[int]) -> list[int]:
    """Update [paren_depth, bracket_depth, brace_depth] for a single non-string character."""
    paren_depth, bracket_depth, brace_depth = depths
    if ch == "(":
        paren_depth += 1
    elif ch == ")" and paren_depth > 0:
        paren_depth -= 1
    elif ch == "[":
        bracket_depth += 1
    elif ch == "]" and bracket_depth > 0:
        bracket_depth -= 1
    elif ch == "{":
        brace_depth += 1
    elif ch == "}" and brace_depth > 0:
        brace_depth -= 1
    return [paren_depth, bracket_depth, brace_depth]


def _normalize_lines(lines: list[str]) -> str:
    return " ".join(line.strip() for line in lines if line.strip()).strip()


def _strip_comments(source: str) -> str:
    def _replace_block(match: re.Match[str]) -> str:
        return "".join("\n" if ch == "\n" else " " for ch in match.group(0))

    source = re.sub(r"/\*.*?\*/", _replace_block, source, flags=re.S)
    source = re.sub(r"//.*$", lambda match: " " * len(match.group(0)), source, flags=re.M)
    return source


def _strip_templates(source: str) -> str:
    def _replace_template(match: re.Match[str]) -> str:
        return "".join("\n" if ch == "\n" else " " for ch in match.group(0))

    return re.sub(r"`(?:\\.|[^`])*`", _replace_template, source, flags=re.S)


def _find_open_brace(line: str) -> int:
    for index, ch in enumerate(line):
        if ch == "{":
            return index
    raise ValueError("Class header is missing an opening brace")
