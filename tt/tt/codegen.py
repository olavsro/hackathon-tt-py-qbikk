"""Python code generator for the Branch B translation engine.

This module consumes the parse-tree contracts from ``contracts/`` and emits
valid Python source. The output is intentionally conservative: supported
TypeScript constructs are translated mechanically, while unsupported lines are
preserved as comments so the generated file remains valid Python.
"""
from __future__ import annotations

import re
from typing import Any

from contracts.parse_tree_schema import ClassNode, MethodNode

from .lib_map import PYTHON_IMPORTS, TS_TYPE_MAP


_BASIC_IMPORTS = [
    "from __future__ import annotations",
    "from typing import Any",
]

_CONTROL_KEYWORDS = ("if ", "elif ", "else", "for ", "while ", "try", "except", "finally")


def generate_python_class(
    class_node: ClassNode,
    import_map: dict[str, str],
) -> str:
    """Return a complete Python class definition as a source string."""
    class_name = class_node["name"]
    base_class = class_node.get("base_class") or "object"
    lines: list[str] = [f"class {class_name}({base_class}):"]

    property_lines = _generate_properties(class_node)
    method_lines = [generate_method(method) for method in class_node.get("methods", [])]

    if not property_lines and not method_lines:
        lines.append("    pass")
    else:
        lines.extend(property_lines)
        if property_lines and method_lines:
            lines.append("")
        for index, method_source in enumerate(method_lines):
            if index > 0:
                lines.append("")
            lines.extend(method_source.splitlines())

    return "\n".join(lines)


def generate_imports(
    used_libraries: list[str],
    import_map: dict[str, str],
) -> str:
    """Return the Python import block as a source string."""
    import_lines = list(_BASIC_IMPORTS)

    for library in used_libraries:
        if library in PYTHON_IMPORTS:
            import_lines.extend(PYTHON_IMPORTS[library])
        elif library in import_map:
            module_path = import_map[library]
            import_lines.append(f"import {module_path}")

    deduped = sorted({line for line in import_lines if line.strip()})
    return "\n".join(deduped)


def camel_to_snake(name: str) -> str:
    """Convert a camelCase identifier to snake_case."""
    step1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    step2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", step1)
    return step2.lower()


def translate_expression(ts_expr: str) -> str:
    """Translate a single TypeScript expression string to Python."""
    expr = ts_expr.strip()
    if not expr:
        return ""

    expr = _strip_trailing_semicolon(expr)
    expr = _strip_await(expr)
    expr = _strip_type_assertions(expr)
    expr = _strip_non_null_assertions(expr)
    expr = expr.replace("this.", "self.")
    expr = re.sub(r"\bnull\b", "None", expr)
    expr = re.sub(r"\btrue\b", "True", expr)
    expr = re.sub(r"\bfalse\b", "False", expr)
    expr = re.sub(r"\bundefined\b", "None", expr)
    expr = _translate_template_literals(expr)
    expr = _translate_object_keys_entries(expr)
    expr = _translate_math_functions(expr)
    expr = _translate_number_functions(expr)
    expr = _translate_array_functions(expr)
    expr = _translate_new_big(expr)
    expr = _translate_nullish_assignment(expr)
    expr = _translate_nullish(expr)
    expr = _translate_optional_chaining(expr)
    expr = _translate_numeric_chain_methods(expr)
    expr = _translate_date_fns(expr)
    expr = _translate_lodash(expr)
    expr = _translate_arrow_functions(expr)
    expr = _translate_ternary(expr)
    expr = _translate_type_keywords(expr)
    return expr


def generate_helper_functions() -> str:
    """Return Python helper functions needed by the generated calculator."""
    lines = []
    lines.append("def each_day_of_interval(start, end):")
    lines.append("    current = start")
    lines.append("    while current <= end:")
    lines.append("        yield current")
    lines.append("        current = current + timedelta(days=1)")
    lines.append("")
    lines.append("def _add_years(d, years):")
    lines.append("    try:")
    lines.append("        return d.replace(year=d.year + years)")
    lines.append("    except ValueError:")
    lines.append("        return d.replace(year=d.year + years, day=28)")
    lines.append("")
    lines.append("def each_year_of_interval(start, end):")
    lines.append("    current = start")
    lines.append("    while current <= end:")
    lines.append("        yield current")
    lines.append("        current = _add_years(current, 1)")
    return "\n".join(lines) + "\n"


def generate_method(method_node: MethodNode) -> str:
    """Generate a Python method definition from a parsed method node."""
    ts_name = method_node["name"]
    method_name = "__init__" if ts_name == "constructor" else camel_to_snake(ts_name)
    params = ["self"]
    for param in method_node.get("params", []):
        expanded = _expand_destructured_param(param["name"], param.get("ts_type", ""))
        params.extend(expanded)
    signature = ", ".join(params)
    return_type = _map_ts_type(method_node.get("return_type", ""))
    header = f"    def {method_name}({signature})"
    if return_type:
        header += f" -> {return_type}"
    header += ":"

    body_lines = _translate_body_lines(method_node.get("body_lines", []))
    if not body_lines:
        body_lines = ["        pass"]

    return "\n".join([header, *body_lines])


def _generate_properties(class_node: ClassNode) -> list[str]:
    lines: list[str] = []
    for prop in class_node.get("properties", []):
        name = camel_to_snake(prop["name"])
        ts_type = _map_ts_type(prop.get("ts_type", ""))
        annotation = f": {ts_type}" if ts_type else ""
        prefix = "    " if not prop.get("is_static") else "    "
        lines.append(f"{prefix}{name}{annotation} = None")
    return lines


def _close_braces(line: str, emitted: list[str], block_stack: list[bool], indent: int) -> tuple[str, int]:
    """Consume leading '}' characters, emitting 'pass' for empty blocks. Returns (remaining_line, new_indent)."""
    while line.startswith("}"):
        if block_stack and not block_stack[-1]:
            emitted.append("    " * (indent + 1) + "pass")
        if block_stack:
            block_stack.pop()
        indent = max(1, indent - 1)
        line = line[1:].strip()
    return line, indent


def _handle_else_branch(line: str, emitted: list[str], block_stack: list[bool], indent: int) -> tuple[str, int]:
    """Rewrite 'else if' -> 'elif' and 'else', popping the block stack. Returns (rewritten_line, new_indent)."""
    if line.startswith("else if "):
        if block_stack and not block_stack[-1]:
            emitted.append("    " * (indent + 1) + "pass")
        if block_stack:
            block_stack.pop()
        indent = max(1, indent - 1)
        line = "elif " + line[len("else if "):]
    elif line.startswith("else"):
        if block_stack and not block_stack[-1]:
            emitted.append("    " * (indent + 1) + "pass")
        if block_stack:
            block_stack.pop()
        indent = max(1, indent - 1)
    return line, indent


def _flush_block_stack(emitted: list[str], block_stack: list[bool], indent: int) -> None:
    """Emit 'pass' for any unclosed empty blocks remaining on the stack."""
    while block_stack:
        if not block_stack.pop():
            emitted.append("    " * (indent + 1) + "pass")
        indent = max(1, indent - 1)


def _translate_body_lines(body_lines: list[str]) -> list[str]:
    emitted: list[str] = []
    indent = 2
    block_stack: list[bool] = []

    for raw_line in body_lines:
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("}"):
            line, indent = _close_braces(line, emitted, block_stack, indent)
            if not line:
                continue

        if line == "{":
            continue

        line, indent = _handle_else_branch(line, emitted, block_stack, indent)

        translated = _translate_statement(line)
        opens_block = translated.rstrip().endswith(":")

        if translated:
            emitted.append("    " * indent + translated)
            if block_stack:
                block_stack[-1] = True
        if opens_block:
            block_stack.append(False)
            indent += 1

    _flush_block_stack(emitted, block_stack, indent)
    return emitted


def _translate_control_flow(stripped: str) -> str | None:
    """Translate if/elif/else/for/while/try/catch/finally keywords. Returns None if not matched."""
    if stripped.startswith("if "):
        condition = _unwrap_parens(stripped[len("if "):]).rstrip("{").strip()
        return f"if {translate_expression(condition)}:"
    if stripped.startswith("elif "):
        condition = _unwrap_parens(stripped[len("elif "):]).rstrip("{").strip()
        return f"elif {translate_expression(condition)}:"
    if stripped.startswith("else"):
        return "else:"
    if stripped.startswith("for "):
        return _translate_for_loop(stripped)
    if stripped.startswith("while "):
        condition = _unwrap_parens(stripped[len("while "):]).rstrip("{").strip()
        return f"while {translate_expression(condition)}:"
    return None


def _translate_exception_handling(stripped: str) -> str | None:
    """Translate try/catch/finally keywords. Returns None if not matched."""
    if stripped.startswith("try"):
        return "try:"
    if stripped.startswith("catch "):
        capture = _unwrap_parens(stripped[len("catch "):]).strip() or "error"
        capture = re.sub(r":\s*\S+$", "", capture).strip() or "error"
        return f"except Exception as {capture}:"
    if stripped.startswith("finally"):
        return "finally:"
    return None


def _translate_statement(line: str) -> str:
    stripped = _strip_trailing_semicolon(line.strip())

    if stripped in ("{", "}"):
        return ""

    if stripped.startswith("async "):
        stripped = stripped[len("async "):].strip()

    if stripped.startswith("return "):
        return f"return {translate_expression(stripped[len('return '):])}"
    if stripped == "return":
        return "return"

    if stripped.startswith("const ") or stripped.startswith("let ") or stripped.startswith("var "):
        return _translate_variable_declaration(stripped)

    control = _translate_control_flow(stripped)
    if control is not None:
        return control

    exception = _translate_exception_handling(stripped)
    if exception is not None:
        return exception

    if stripped.startswith("//"):
        return f"# {stripped[2:].strip()}"

    nullish_assign = re.match(r"^(\S+)\s*\?\?=\s*(.+)$", stripped)
    if nullish_assign:
        target = translate_expression(nullish_assign.group(1))
        value = translate_expression(nullish_assign.group(2))
        return f"if {target} is None: {target} = {value}"

    translated = translate_expression(stripped)
    if translated:
        return translated
    return f"# ts: {stripped}"


def _translate_object_destructure(fields_raw: str, value: str) -> str:
    """Translate object destructuring fields into semicolon-separated Python assignments."""
    field_names = _parse_destructure_fields(fields_raw)
    if "." not in value:
        parts = [f"{camel_to_snake(f)} = {value}.get('{f}')" for f in field_names]
    else:
        parts = [f"{camel_to_snake(f)} = {value}['{f}']" for f in field_names]
    return "; ".join(parts)


def _translate_array_destructure(fields_raw: str, value: str) -> str:
    """Translate array destructuring fields into a tuple-unpack Python assignment."""
    targets = ", ".join(camel_to_snake(f.strip()) for f in fields_raw.split(","))
    return f"{targets} = {value}"


def _translate_typed_assignment(match: re.Match[str]) -> str:
    """Translate a simple typed or untyped variable assignment match."""
    name = _normalize_identifier(match.group("name"))
    value = translate_expression(match.group("value"))
    ts_type = match.group("ts_type")
    if ts_type:
        py_type = _map_ts_type(ts_type)
        if py_type:
            return f"{name}: {py_type} = {value}"
    return f"{name} = {value}"


def _translate_variable_declaration(line: str) -> str:
    line = re.sub(r"^(const|let|var)\s+", "", line)

    no_init = re.match(r"^(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*(?::\s*(?P<ts_type>.+?))?$", line.strip())
    if no_init:
        name = camel_to_snake(no_init.group("name"))
        ts_type = no_init.group("ts_type") or ""
        py_type = _map_ts_type(ts_type)
        if py_type:
            return f"{name}: {py_type} = None"
        return f"{name} = None"

    destructure = re.match(r"^\{(?P<fields>[^}]+)\}\s*(?::[^=]+)?\s*=\s*(?P<value>.+)$", line.strip())
    if destructure:
        value = translate_expression(destructure.group("value"))
        return _translate_object_destructure(destructure.group("fields"), value)

    arr_destructure = re.match(r"^\[(?P<fields>[^\]]+)\]\s*(?::[^=]+)?\s*=\s*(?P<value>.+)$", line.strip())
    if arr_destructure:
        value = translate_expression(arr_destructure.group("value"))
        return _translate_array_destructure(arr_destructure.group("fields"), value)

    match = re.match(r"(?P<name>[^:=]+?)(?::\s*(?P<ts_type>.+?))?\s*=\s*(?P<value>.+)$", line)
    if not match:
        return f"# ts: {line}"
    return _translate_typed_assignment(match)


def _translate_c_style_for(loop: str) -> str | None:
    """Translate a C-style for loop (let i = 0; i < n; i++) into a Python range loop."""
    c_style = re.match(
        r"(let|var|const)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\d+);\s*\2\s*<\s*(.+?);\s*\2\s*(?:\+=\s*(\d+)|(\+\+))",
        loop,
    )
    if not c_style:
        return None
    var = camel_to_snake(c_style.group(2))
    start = c_style.group(3)
    end = translate_expression(c_style.group(4))
    step = c_style.group(5) or "1"
    if step == "1":
        return f"for {var} in range({start}, {end}):"
    return f"for {var} in range({start}, {end}, {step}):"


def _translate_for_of_target(raw_target: str, iterable: str) -> str:
    """Translate the target variable(s) of a for...of loop into a Python for statement."""
    if raw_target.startswith("{") and raw_target.endswith("}"):
        inner = raw_target[1:-1]
        field_names = _parse_destructure_fields(inner)
        target = ", ".join(camel_to_snake(f) for f in field_names)
        return f"for {target} in ({iterable}):"
    if raw_target.startswith("[") and raw_target.endswith("]"):
        inner = raw_target[1:-1]
        parts = [camel_to_snake(p.strip()) for p in inner.split(",")]
        target = ", ".join(parts)
        return f"for {target} in {iterable}:"
    target = _normalize_identifier(raw_target)
    return f"for {target} in {iterable}:"


def _translate_for_of(loop: str, original_line: str) -> str:
    """Translate a for...of loop into a Python for loop."""
    match = re.match(r"(const|let|var)\s+(.+?)\s+of\s+(.+)", loop)
    if not match:
        return f"# ts: {original_line}"
    raw_target = match.group(2).strip()
    iterable_raw = match.group(3).strip()

    entries_match = re.match(r"^(.+?)\.entries\(\)$", iterable_raw)
    if entries_match:
        iterable = translate_expression(entries_match.group(1))
        if raw_target.startswith("[") and raw_target.endswith("]"):
            inner = raw_target[1:-1]
            parts = [camel_to_snake(p.strip()) for p in inner.split(",")]
            target = ", ".join(parts)
        else:
            target = _normalize_identifier(raw_target)
        return f"for {target} in enumerate({iterable}):"

    iterable = translate_expression(iterable_raw)
    return _translate_for_of_target(raw_target, iterable)


def _translate_for_loop(line: str) -> str:
    loop = re.sub(r"^for\s*", "", line).rstrip("{").strip()
    loop = _unwrap_parens(loop)

    c_result = _translate_c_style_for(loop)
    if c_result is not None:
        return c_result

    if re.match(r"(const|let|var)\s+.+\s+of\s+", loop):
        return _translate_for_of(loop, line)

    return f"# ts: {line}"


def _format_parameter(name: str, ts_type: str) -> str:
    normalized = _normalize_identifier(name)
    py_type = _map_ts_type(ts_type)
    if py_type:
        return f"{normalized}: {py_type}"
    return normalized


def _map_ts_type(ts_type: str) -> str:
    cleaned = ts_type.strip()
    if not cleaned:
        return ""
    if cleaned in TS_TYPE_MAP:
        return TS_TYPE_MAP[cleaned]
    cleaned = cleaned.replace("Array<", "list[").replace(">", "]")
    cleaned = re.sub(r"Record<string,\s*(.+)>", r"dict[str, \1]", cleaned)
    cleaned = re.sub(r"\{\s*\[key:\s*string\]:\s*(.+)\}", r"dict[str, \1]", cleaned)
    cleaned = cleaned.replace("Promise<", "").replace(">", "")
    cleaned = cleaned.replace("Big", "Decimal")
    cleaned = cleaned.replace("boolean", "bool")
    cleaned = cleaned.replace("number", "float")
    cleaned = cleaned.replace("string", "str")
    cleaned = cleaned.replace("Date", "datetime")
    cleaned = cleaned.replace("any", "Any")
    cleaned = cleaned.replace("void", "None")
    return cleaned


def _normalize_identifier(name: str) -> str:
    normalized = name.strip()
    if normalized.startswith("{") and normalized.endswith("}"):
        inner = normalized[1:-1].strip()
        fields = _parse_destructure_fields(inner)
        return ", ".join(camel_to_snake(f) for f in fields)
    if normalized.startswith("[") and normalized.endswith("]"):
        inner = normalized[1:-1].strip()
        parts = [camel_to_snake(p.strip()) for p in inner.split(",")]
        return ", ".join(parts)
    return camel_to_snake(normalized) if re.match(r"[a-z]+[A-Z]", normalized) else normalized


def _parse_destructure_fields(inner: str) -> list[str]:
    """Parse fields from a destructured object literal like 'a, b: aliasB, c'."""
    fields: list[str] = []
    for part in inner.split(","):
        part = part.strip()
        if not part:
            continue
        # Handle renaming: { key: localName } - take the localName
        if ":" in part:
            local = part.split(":", 1)[1].strip()
        else:
            local = part
        # Strip default values: field = default
        local = local.split("=")[0].strip()
        if local:
            fields.append(local)
    return fields


def _expand_destructured_param(name: str, ts_type: str) -> list[str]:
    """Expand a destructured object parameter into individual Python params."""
    stripped = name.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        inner = stripped[1:-1].strip()
        fields = _parse_destructure_fields(inner)
        result = []
        for f in fields:
            py_name = camel_to_snake(f)
            result.append(py_name)
        return result
    # Normal parameter
    return [_format_parameter(name, ts_type)]


def _strip_await(expr: str) -> str:
    """Remove 'await' keyword from expressions (async TS → sync Python)."""
    return re.sub(r"\bawait\s+", "", expr)


def _strip_type_assertions(expr: str) -> str:
    """Remove TypeScript 'as Type' type assertions."""
    # Handle: expr as Type (but not inside strings/templates)
    # Remove ' as TypeName' where TypeName is an identifier or generic
    return re.sub(r"\s+as\s+[A-Za-z_][A-Za-z0-9_<>\[\]|&,\s]*(?=[,)\]};:\s]|$)", "", expr)


def _strip_non_null_assertions(expr: str) -> str:
    """Remove TypeScript non-null assertion operator '!'.

    The non-null assertion '!' appears directly after an identifier/paren/bracket
    and is NOT followed by '=' (which would make it part of '!=' or '!==').
    """
    return re.sub(r"([A-Za-z0-9_\]\)])!(?!=)", r"\1", expr)


def _translate_nullish_assignment(expr: str) -> str:
    """Translate '??=' nullish assignment in expression context - handled in statement."""
    return expr


def _translate_math_functions(expr: str) -> str:
    """Translate Math.* calls to Python builtins."""
    expr = re.sub(r"\bMath\.abs\(", "abs(", expr)
    expr = re.sub(r"\bMath\.min\(", "min(", expr)
    expr = re.sub(r"\bMath\.max\(", "max(", expr)
    expr = re.sub(r"\bMath\.floor\(", "math.floor(", expr)
    expr = re.sub(r"\bMath\.ceil\(", "math.ceil(", expr)
    expr = re.sub(r"\bMath\.round\(", "round(", expr)
    expr = re.sub(r"\bMath\.sqrt\(", "math.sqrt(", expr)
    expr = re.sub(r"\bMath\.pow\(([^,]+),\s*([^)]+)\)", r"(\1 ** \2)", expr)
    expr = re.sub(r"\bMath\.PI\b", "math.pi", expr)
    expr = re.sub(r"\bNumber\.EPSILON\b", "sys.float_info.epsilon", expr)
    expr = re.sub(r"\bNumber\.isFinite\(", "math.isfinite(", expr)
    expr = re.sub(r"\bNumber\.isNaN\(", "math.isnan(", expr)
    expr = re.sub(r"\bNumber\.MAX_SAFE_INTEGER\b", "9007199254740991", expr)
    return expr


def _translate_number_functions(expr: str) -> str:
    """Translate Number(), parseInt(), parseFloat() to Python equivalents."""
    expr = re.sub(r"\bNumber\(([^)]+)\)", r"float(\1)", expr)
    expr = re.sub(r"\bparseInt\(([^,)]+)(?:,\s*\d+)?\)", r"int(\1)", expr)
    expr = re.sub(r"\bparseFloat\(([^)]+)\)", r"float(\1)", expr)
    expr = re.sub(r"\bString\(([^)]+)\)", r"str(\1)", expr)
    expr = re.sub(r"\bBoolean\(([^)]+)\)", r"bool(\1)", expr)
    return expr


def _translate_array_functions(expr: str) -> str:
    """Translate Array.isArray() and spread syntax."""
    expr = re.sub(r"\bArray\.isArray\(([^)]+)\)", r"isinstance(\1, list)", expr)
    return expr


def _translate_ternary(expr: str) -> str:
    """Translate TypeScript ternary 'cond ? a : b' to Python 'a if cond else b'."""
    # Only translate if there's exactly one unambiguous ? and matching :
    # Use a simple pattern that avoids optional chaining (?.) and nullish (??)
    # Strategy: find pattern "... ? ... : ..." not preceded by '?' or followed by '?' or '.'
    try:
        result = _convert_ternary(expr)
        return result
    except Exception:
        return expr


def _find_ternary_question(expr: str) -> int:
    """Return the index of the first unambiguous '?' in expr at depth 0, or -1."""
    depth = 0
    for i, c in enumerate(expr):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "?" and depth == 0:
            next_c = expr[i + 1] if i + 1 < len(expr) else ""
            if next_c not in (".", "?"):
                return i
    return -1


def _find_ternary_colon(rest: str) -> int:
    """Return the index of the matching ':' in *rest* (the part after '?') at depth 0, or -1."""
    depth = 0
    for j, c in enumerate(rest):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == ":" and depth == 0:
            return j
    return -1


def _convert_ternary(expr: str) -> str:
    """Convert C-style ternary to Python ternary, respecting nesting."""
    q_pos = _find_ternary_question(expr)
    if q_pos == -1:
        return expr

    condition = expr[:q_pos].strip()
    rest = expr[q_pos + 1:]

    c_pos = _find_ternary_colon(rest)
    if c_pos == -1:
        return expr

    true_branch = rest[:c_pos].strip()
    false_branch = rest[c_pos + 1:].strip()

    py_cond = translate_expression(condition)
    py_true = translate_expression(true_branch)
    py_false = translate_expression(false_branch)

    return f"({py_true} if {py_cond} else {py_false})"


def _translate_new_big(expr: str) -> str:
    return re.sub(r"new\s+Big\((.+?)\)", r"Decimal(str(\1))", expr)


def _translate_numeric_chain_methods(expr: str) -> str:
    patterns = {
        "plus": "+",
        "add": "+",
        "minus": "-",
        "sub": "-",
        "times": "*",
        "mul": "*",
        "div": "/",
        "eq": "==",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
    }
    for method, operator in patterns.items():
        expr = re.sub(
            rf"([A-Za-z0-9_\]\)\.]+)\.{method}\((.+?)\)",
            rf"(\1 {operator} \2)",
            expr,
        )
    expr = re.sub(r"([A-Za-z0-9_\]\)\.]+)\.toNumber\(\)", r"float(\1)", expr)
    expr = re.sub(r"([A-Za-z0-9_\]\)\.]+)\.toFixed\((.+?)\)", r"format(\1, f'.{\2}f')", expr)
    expr = re.sub(r"([A-Za-z0-9_\]\)\.]+)\.length\b", r"len(\1)", expr)
    expr = expr.replace(".includes(", ".__contains__(")
    return expr


def _translate_date_fns(expr: str) -> str:
    replacements = {
        "differenceInDays(": "difference_in_days(",
        "eachDayOfInterval(": "each_day_of_interval(",
        "eachYearOfInterval(": "each_year_of_interval(",
        "isBefore(": "is_before(",
        "isAfter(": "is_after(",
        "isWithinInterval(": "is_within_interval(",
        "startOfDay(": "start_of_day(",
        "endOfDay(": "end_of_day(",
        "startOfYear(": "start_of_year(",
        "endOfYear(": "end_of_year(",
        "addMilliseconds(": "add_milliseconds(",
    }
    for old, new in replacements.items():
        expr = expr.replace(old, new)
    expr = re.sub(r"format\((.+?),\s*DATE_FORMAT\)", r"\1.strftime('%Y-%m-%d')", expr)
    # addDays / subDays → timedelta arithmetic
    expr = re.sub(r"\baddDays\(([^,]+),\s*([^)]+)\)", r"(\1 + timedelta(days=\2))", expr)
    expr = re.sub(r"\bsubDays\(([^,]+),\s*([^)]+)\)", r"(\1 - timedelta(days=\2))", expr)
    return expr


def _translate_lodash(expr: str) -> str:
    expr = expr.replace("cloneDeep(", "copy.deepcopy(")
    expr = re.sub(r"sortBy\((.+?),\s*(.+)\)", r"sorted(\1, key=\2)", expr)
    expr = re.sub(r"sum\((.+)\)", r"sum(\1)", expr)
    expr = re.sub(r"uniqBy\((.+?),\s*(.+)\)", r"uniq_by(\1, \2)", expr)
    expr = re.sub(r"isNumber\((.+)\)", r"isinstance(\1, (int, float))", expr)
    return expr


def _translate_object_keys_entries(expr: str) -> str:
    expr = re.sub(r"Object\.keys\((.+?)\)", r"list(\1.keys())", expr)
    expr = re.sub(r"Object\.entries\((.+?)\)", r"list(\1.items())", expr)
    expr = re.sub(r"Object\.values\((.+?)\)", r"list(\1.values())", expr)
    return expr


def _translate_arrow_functions(expr: str) -> str:
    expr = re.sub(r"\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*=>\s*([^,)\]}]+)", r"lambda \1: \2", expr)
    expr = re.sub(r"([A-Za-z_][A-Za-z0-9_]*)\s*=>\s*([^,)\]}]+)", r"lambda \1: \2", expr)
    return expr


def _translate_template_literals(expr: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        template = match.group(1)
        return f'f"{template}"'

    return re.sub(r"`([^`]*)`", _replace, expr)


def _translate_optional_chaining(expr: str) -> str:
    for _ in range(50):  # safety cap: break if no regex matched (unhandled ?. pattern)
        if "?." not in expr:
            break
        new_expr = re.sub(
            r"([A-Za-z0-9_\]\)]+)\?\.\[([^\]]+)\]",
            r"(\1.get(\2) if \1 is not None else None)",
            expr,
        )
        new_expr = re.sub(
            r"([A-Za-z0-9_\]\)]+)\?\.([A-Za-z_][A-Za-z0-9_]*)",
            r"(getattr(\1, '\2', None) if \1 is not None else None)",
            new_expr,
        )
        if new_expr == expr:
            break  # no substitution made — remaining ?. is in an unhandled context
        expr = new_expr
    return expr


def _translate_nullish(expr: str) -> str:
    return re.sub(r"(.+?)\s*\?\?\s*(.+)", r"(\1 if \1 is not None else \2)", expr)


def _translate_type_keywords(expr: str) -> str:
    expr = expr.replace("&&", " and ")
    expr = expr.replace("||", " or ")
    expr = expr.replace("!==", " != ")
    expr = re.sub(r"(?<![=!<>])===(?!=)", " == ", expr)
    # Logical NOT: standalone '!' prefix (not part of '!=' or '!.')
    expr = re.sub(r"(?<![=!<>])!(?![=.])\s*([A-Za-z_(])", r"not \1", expr)
    # Spread operator: ...obj → **obj (works for both dict and iterable unpacking)
    expr = re.sub(r"\.\.\.\s*([A-Za-z_][A-Za-z0-9_.]*)", r"**\1", expr)
    return expr


def _unwrap_parens(text: str) -> str:
    value = text.strip()
    if value.startswith("(") and value.endswith(")"):
        return value[1:-1].strip()
    return value


def _strip_trailing_semicolon(text: str) -> str:
    return text[:-1].rstrip() if text.endswith(";") else text
