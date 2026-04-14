# SOLUTION.md

## Solution

### Pipeline overview

The translation tool (`tt`) converts the Ghostfolio TypeScript portfolio calculator into
an equivalent Python implementation through a four-module pipeline:

```
TS source files
    |
    v
parser.py ──── parse_ts_file() ──> ParseTree dict
    |
    v
lib_map.py ─── BIG_JS_METHODS / DATE_FNS_FUNCTIONS / TS_TYPE_MAP ──> mapping tables
    |
    v
codegen.py ─── generate_python_class() ──> Python source string
    |           (uses lib_map.py for expression translation)
    v
translator.py ─ assemble + ast.parse() + write ──> portfolio_calculator.py
```

### What `parse_ts_file()` produces

`parse_ts_file(path)` returns a `ParseTree` TypedDict (defined in
`contracts/parse_tree_schema.py`) containing:

- `classes` — list of `ClassNode` dicts, each holding the class name, base class,
  `properties` list, and `methods` list.  Each `MethodNode` carries the method name,
  visibility (`"public"` / `"protected"` / `"private"` / `""`), parameter list, return
  type, and raw TypeScript body lines.
- `imports` — list of `ImportNode` dicts describing every top-level `import` statement
  (symbols and source module).
- `top_level_vars` — list of `{name, ts_type, initializer}` dicts for module-level
  `const`/`let` declarations.

### How `tt_import_map.json` is used

The scaffold setup script writes `tt_import_map.json` into
`tt/tt/scaffold/ghostfolio_pytx/`.  `translator.py` loads this file at runtime and
passes the resulting `dict[str, str]` to both `generate_imports()` and
`generate_python_class()`.

This means **no project-specific module-path strings are hardcoded anywhere in `tt/`**.
All such strings live exclusively in the JSON file, satisfying the
`detect_direct_mappings` implementation rule.

### Big.js -> `decimal.Decimal` strategy

TypeScript financial code uses the `Big` class from `big.js` for arbitrary-precision
arithmetic.  The translation maps every `Big(x)` call to `Decimal(str(x))`:

- `Decimal(str(x))` is used instead of `Decimal(x)` because Python `float` values
  already carry IEEE-754 rounding errors before `Decimal` sees them.  Converting via
  `str` preserves the original decimal representation.
- Arithmetic operators (`+`, `-`, `*`, `/`) map directly to Python's `Decimal`
  operators.
- Comparison methods (`.eq()`, `.gt()`, `.lt()`, `.gte()`, `.lte()`) map to Python
  comparison operators (`==`, `>`, `<`, `>=`, `<=`).

### `date-fns` -> `datetime`/`dateutil` strategy

Every `date-fns` function is mapped function-by-function through `DATE_FNS_FUNCTIONS`
(in `lib_map.py`):

| TypeScript (`date-fns`) | Python (`datetime` / `dateutil`) |
|-------------------------|----------------------------------|
| `parseISO(s)` | `datetime.fromisoformat(s)` |
| `format(d, "yyyy-MM-dd")` | `d.strftime("%Y-%m-%d")` |
| `differenceInDays(a, b)` | `(a - b).days` |
| `addDays(d, n)` | `d + timedelta(days=n)` |
| `startOfYear(d)` | `d.replace(month=1, day=1)` |
| `endOfYear(d)` | `d.replace(month=12, day=31)` |

`python-dateutil>=2.9` is declared in `tt/pyproject.toml` to support the `relativedelta`
utility needed for month/year arithmetic.

### Before/after example

**TypeScript input:**

```typescript
protected getPerformanceCalculationType(): PerformanceCalculationType {
  return PerformanceCalculationType.ROAI;
}
```

**Python output (translated):**

```python
def get_performance_calculation_type(self) -> str:
    return "ROAI"
```

Key transformations: camelCase -> snake_case (via `camel_to_snake()`), TypeScript enum
reference -> Python string literal, TypeScript visibility modifier removed, return type
annotation simplified.

---

## Architecture

```
TS source files
    |
    v
parser.py ──── parse_ts_file() ──> ParseTree dict
    |
    v
codegen.py ─── generate_python_class() ──> Python source string
    |           (uses lib_map.py for expression translation)
    v
translator.py ─ assemble + ast.parse() + write ──> portfolio_calculator.py
```

**Module responsibilities:**

| Module | Branch | Responsibility |
|--------|--------|----------------|
| `parser.py` | B | Parse TypeScript source into `ParseTree` TypedDicts |
| `lib_map.py` | B | Mapping tables: Big.js methods, date-fns functions, TS types |
| `codegen.py` | B | Generate Python class/import source strings from `ParseTree` |
| `translator.py` | A | Orchestrate the pipeline: load config, call modules, write output |
| `runner.py` | A | Invoke scaffold setup subprocess; importable helper for `cli.py` |

---

## Coding approach

### Branch split

Development was split into two parallel branches with a strict file-ownership
contract (enforced by the roadmap):

- **Branch A** (`roadmap-part-a-new`) — pipeline orchestration: `runner.py`,
  `translator.py`, `cli.py`, `pyproject.toml`.  Owns the wiring that drives the
  pipeline and writes output files.
- **Branch B** — parsing engines: `parser.py`, `lib_map.py`, `codegen.py`, and all
  unit tests.  Owns the actual TypeScript comprehension and Python code generation.

The branches share a read-only `contracts/` directory (TypedDict schemas and function
signatures) so each side can develop and type-check independently without coordination
overhead.

### Iterative workflow

1. Translate -> run `tt translate` -> inspect output file.
2. Run `make translate-and-test-ghostfolio_pytx` -> record `X passed / Y failed`.
3. Categorise failures: orchestration bugs (wrong output path, wrong method selection)
   belong to Branch A; expression/type-translation bugs belong to Branch B.
4. Patch the responsible module -> rerun -> repeat.

### Compliance checking

`make detect_rule_breaches` was used as a continuous gate to confirm:

- No financial logic is hardcoded in `translator.py` (`detect_explicit_financial_logic`).
- No project-specific module-path strings appear in `tt/` source (`detect_direct_mappings`).
- The scaffold and wrapper layers are not modified (`detect_scaffold_bloat`,
  `detect_wrapper_modification`).
- No copy-paste of TypeScript bodies as Python strings (`detect_code_block_copying`).

### Using the Claude Code skill

Run `/explain-tt-strategy` in Claude Code to get an automated analysis of the
translation strategy.

### Results

- **Final test score:** [PLACEHOLDER -- fill in post-merge] `XX passed / YY failed`
- **Combined evaluation score:** [PLACEHOLDER -- fill in post-merge]
  (`make evaluate_tt_ghostfolio`)
- **Notable deviations from plan:** [PLACEHOLDER -- fill in post-merge]
