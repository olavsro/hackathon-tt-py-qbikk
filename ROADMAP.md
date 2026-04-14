# ROADMAP.md — TT: TypeScript → Python Translation Tool

---

## Project Overview

**Project name:** tt — TypeScript-to-Python Translation Tool

**One-sentence description:** A Python-based translation tool that transpiles the Ghostfolio ROAI portfolio calculator from TypeScript to idiomatic Python, enabling the translated code to pass the full API test suite.

**Tech stack:**
- Python 3.11+
- `uv` for dependency/env management (`pyproject.toml`)
- `FastAPI` + `uvicorn` for the translated server
- `decimal.Decimal` (replaces `big.js`)
- `python-dateutil` / `datetime` (replaces `date-fns`)
- `pytest` + `requests` for API tests
- Standard library only inside `tt/` (no LLMs, no Node.js)

**Repository structure:**

```
tt/                          ← translation tool source (this is what we build)
  tt/
    cli.py                   ← entry-point: `tt translate`
    translator.py            ← orchestrates the full pipeline
    parser.py                ← TypeScript AST/regex parser (NEW — M2)
    lib_map.py               ← library mapping tables (NEW — M3)
    codegen.py               ← Python source generator (NEW — M4)
    runner.py                ← scaffold setup helper (NEW — M1)
    __init__.py
    __main__.py
  pyproject.toml

translations/
  ghostfolio_pytx/           ← tt output (generated, do not edit by hand)
    app/
      main.py                ← immutable wrapper (copied verbatim)
      wrapper/               ← immutable wrapper layer (copied verbatim)
      implementation/        ← tt-generated code only
        portfolio/calculator/roai/portfolio_calculator.py

  ghostfolio_pytx_example/   ← handwritten reference skeleton (read-only)

projects/
  ghostfolio/                ← original TypeScript source (read-only)
    apps/api/src/app/portfolio/calculator/roai/portfolio-calculator.ts
    apps/api/src/app/portfolio/calculator/portfolio-calculator.ts

projecttests/
  ghostfolio_api/            ← API test suite (read-only)

helptools/
  setup_ghostfolio_scaffold_for_tt.py

make/                        ← Makefile fragments
```

**Bootstrap & run locally:**

```bash
# 1. Translate
uv run --project tt tt translate

# 2. Spin up server + run tests
make translate-and-test-ghostfolio_pytx

# 3. Full evaluation (tests 85% + code quality 15%)
make evaluate_tt_ghostfolio

# 4. Check rule compliance
make detect_rule_breaches

# 5. Publish results
make publish_results
```

**Dependency management:** `uv` with `pyproject.toml` inside `tt/`. All runtime deps declared under `[project.dependencies]`.

---

## Competition Rules Summary (binding constraints on every milestone)

From `COMPETITION_RULES.md`:

1. **No LLMs** in the translation path — `tt/` must contain zero LLM API calls.
2. **No pre-written domain logic** — translated code must come from actual TypeScript translation, not a hand-crafted stub copied from `ghostfolio_pytx_example`.
3. **No project-specific hardcoded paths** in `tt/` core — use `tt_import_map.json` inside the scaffold directory.
4. **Wrapper files are immutable** — `app/main.py` and `app/wrapper/` must be byte-for-byte identical to `ghostfolio_pytx_example`.
5. **Translation output only in `app/implementation/`** — nothing outside that directory may be written by `tt`.
6. **Pure Python translation** — no shell calls to `node`, `tsc`, or other JS runtimes.
7. **Rule checker:** `make detect_rule_breaches` must pass clean before submission.
8. **Frequent commits** — git log must show gradual development progress.

---

## Milestone 1 — Establish Project Scaffold and Runner Infrastructure

**Status:** [ ] Not started
**Agent:** Agent-Infra
**Dependencies:** None
**Scope:** `tt/tt/runner.py`, `tt/pyproject.toml`, `tt/tt/scaffold/ghostfolio_pytx/tt_import_map.json`
**Merge strategy:** New files only; does not touch `translator.py`, `cli.py`, or any translation logic.

### Goal
Formalise the scaffold setup pipeline and introduce the `tt_import_map.json` contract so all later milestones have a stable, rule-compliant project configuration to build on. This milestone also adds `python-dateutil` as a declared dependency.

### Tasks
- [ ] Read `helptools/setup_ghostfolio_scaffold_for_tt.py` in full to understand current scaffold flow.
- [ ] Create `tt/tt/runner.py` that exposes `setup_scaffold(repo_root, output_dir)` — refactors the subprocess call in `cli.py` into an importable function.
- [ ] Create `tt/tt/scaffold/ghostfolio_pytx/tt_import_map.json` with an empty `{}` object as placeholder (filled in M3).
- [ ] Update `tt/pyproject.toml` to add `python-dateutil>=2.9` to `[project.dependencies]`.
- [ ] Update `tt/tt/cli.py` to call `runner.setup_scaffold()` instead of `subprocess.run(setup_script)`.
- [ ] Verify `uv run --project tt tt translate` still completes without error after the refactor.

### Acceptance criteria
- `runner.setup_scaffold()` can be imported and called standalone without subprocess.
- `tt_import_map.json` exists at the correct path and is valid JSON.
- `uv run --project tt tt translate` exits 0 and produces output at `translations/ghostfolio_pytx/`.
- `make detect_rule_breaches` shows no new violations introduced by this milestone.

### Verification steps
- [ ] `python -c "from tt.runner import setup_scaffold; print('ok')"`
- [ ] `python -c "import json; json.load(open('tt/tt/scaffold/ghostfolio_pytx/tt_import_map.json'))"`
- [ ] `uv run --project tt tt translate` exits with code 0
- [ ] `make detect_rule_breaches` — review output for new violations

### Changelog entry (fill in on completion)
- **Completed:** —
- **What was done:** —
- **Deviations from plan:** —
- **Notes for next roadmap:** —

---

## Milestone 2 — Build the TypeScript Parser

**Status:** [ ] Not started
**Agent:** Agent-Parser
**Dependencies:** Milestone 1
**Scope:** `tt/tt/parser.py` (new file only)
**Merge strategy:** New file; no modifications to any existing file in `tt/tt/`.

### Goal
Produce a parser that reads a TypeScript source file and returns a structured Python dictionary (the "parse tree") representing classes, methods, properties, and expressions. This parse tree is the single interface consumed by M4 (codegen). Getting this right is the critical path for correctness.

The two target files to parse are:
- `projects/ghostfolio/apps/api/src/app/portfolio/calculator/roai/portfolio-calculator.ts`
- `projects/ghostfolio/apps/api/src/app/portfolio/calculator/portfolio-calculator.ts`

### Tasks
- [ ] Read both TypeScript source files in full and catalogue every syntactic pattern that appears (class declarations, method signatures, variable declarations, for-of loops, if/else, ternary expressions, arrow functions, template literals, `new Big(...)`, `format(...)`, etc.).
- [ ] Design the parse-tree schema as a Python `TypedDict` or plain dict with keys: `classes`, `imports`, `top_level_vars`. Document schema in module docstring.
- [ ] Implement `parse_ts_file(path: Path) -> dict` using regex + light string analysis (no external AST libs needed unless complexity demands it; `tree-sitter` Python bindings are allowed if helpful).
- [ ] Handle TypeScript-specific constructs:
  - `import { X } from 'y'` → capture symbol list + module string
  - `export class Foo extends Bar { ... }` → class name, base class
  - `private/protected/public methodName(params): ReturnType { body }` → method dict
  - `const x = new Big(0)` → variable with initializer
  - `for (const item of collection)` → for-of loop node
  - `?.` optional chaining → safe navigation
  - `: { [key: string]: Big }` index signature types → `dict[str, Decimal]`
  - `Big` arithmetic chain (`.plus()`, `.minus()`, `.times()`, `.div()`, `.eq()`, `.toNumber()`) → method call nodes
- [ ] Implement `extract_class_methods(parse_tree: dict, class_name: str) -> list[dict]` returning list of `{name, params, body_lines, return_type}`.
- [ ] Write unit tests in `tt/tests/test_parser.py` covering each pattern above using inline TS snippets (no file I/O needed in tests).

### Acceptance criteria
- `parse_ts_file` successfully parses both target TS files without raising exceptions.
- `extract_class_methods` returns at least the following methods from `portfolio-calculator.ts`: `getSymbolMetrics`, `calculateOverallPerformance`, `getPerformanceCalculationType`, `getInvestments`, `getSnapshot`, `getChartData`.
- Unit tests pass: `pytest tt/tests/test_parser.py -v`.

### Verification steps
- [ ] `pytest tt/tests/test_parser.py -v` — all tests pass
- [ ] `python -c "from tt.parser import parse_ts_file; from pathlib import Path; r = parse_ts_file(Path('projects/ghostfolio/apps/api/src/app/portfolio/calculator/roai/portfolio-calculator.ts')); print([c['name'] for c in r['classes']])"`
- [ ] Verify `RoaiPortfolioCalculator` appears in the printed class list
- [ ] `make detect_rule_breaches` — no new violations

### Changelog entry (fill in on completion)
- **Completed:** —
- **What was done:** —
- **Deviations from plan:** —
- **Notes for next roadmap:** —

---

## Milestone 3 — Build the Library Mapping Tables

**Status:** [ ] Not started
**Agent:** Agent-LibMap
**Dependencies:** Milestone 1
**Scope:** `tt/tt/lib_map.py` (new file), `tt/tt/scaffold/ghostfolio_pytx/tt_import_map.json` (populated)
**Merge strategy:** New file + update to `tt_import_map.json` (created empty in M1). No overlap with M2 (`parser.py`).

### Goal
Provide the complete, rule-compliant mapping tables that the code generator (M4) uses to translate TypeScript library calls into Python equivalents. This covers `big.js`, `date-fns`, `lodash`, TypeScript built-ins, and the `@ghostfolio/` import namespace.

### Tasks
- [ ] Read `projects/ghostfolio/apps/api/src/app/portfolio/calculator/roai/portfolio-calculator.ts` and `portfolio-calculator.ts` to inventory every external library call actually used.
- [ ] Implement `tt/tt/lib_map.py` with the following mapping dicts (all pure data, no logic):
  - `BIG_JS_METHODS: dict[str, str]` — e.g. `"plus" → "+"`, `"minus" → "-"`, `"times" → "*"`, `"div" → "/"`, `"eq" → "=="`, `"gt" → ">"`, `"lt" → "<"`, `"toNumber" → "float(...)"`, `"toFixed" → "format(...)"`
  - `DATE_FNS_FUNCTIONS: dict[str, str]` — e.g. `"format" → "format"` (dateutil), `"differenceInDays" → "(b - a).days"`, `"eachDayOfInterval" → "date_range"`, `"eachYearOfInterval" → "year_range"`, `"isBefore" → "<"`, `"isAfter" → ">"`, `"startOfDay" → "date.replace(hour=0,...)"`, `"endOfDay" → ...`, `"subDays" → "timedelta(days=...)"`, `"addMilliseconds" → "timedelta(milliseconds=...)"`, `"isWithinInterval" → "..."`
  - `LODASH_FUNCTIONS: dict[str, str]` — e.g. `"sortBy" → "sorted(..., key=...)"`, `"cloneDeep" → "copy.deepcopy"`, `"sum" → "sum"`, `"uniqBy" → "..."`, `"isNumber" → "isinstance(..., (int, float))"`
  - `TS_TYPE_MAP: dict[str, str]` — e.g. `"Big" → "Decimal"`, `"string" → "str"`, `"number" → "float"`, `"boolean" → "bool"`, `"void" → "None"`, `"any" → "Any"`, `"Date" → "date"`, `"Record<string, X>" → "dict[str, X]"`, `"{ [key: string]: X }" → "dict[str, X]"`
  - `PYTHON_IMPORTS: dict[str, list[str]]` — for each mapping category, the Python imports needed (e.g. `"decimal" → ["from decimal import Decimal"]`, `"dateutil" → ["from datetime import date, timedelta", "from dateutil.relativedelta import relativedelta"]`)
- [ ] Populate `tt/tt/scaffold/ghostfolio_pytx/tt_import_map.json` with all `@ghostfolio/` import paths found in the two TS files, mapping each to the Python module path it resolves to inside `app/wrapper/` or `app/implementation/`. Example: `"@ghostfolio/api/app/portfolio/calculator/portfolio-calculator" → "app.wrapper.portfolio.calculator.portfolio_calculator"`.
- [ ] Write `tt/tests/test_lib_map.py` with assertions that each mapping dict is non-empty and has no keys with typos (spot-check a known method in each dict).

### Acceptance criteria
- `from tt.lib_map import BIG_JS_METHODS, DATE_FNS_FUNCTIONS, LODASH_FUNCTIONS, TS_TYPE_MAP, PYTHON_IMPORTS` imports without error.
- Every Big.js method found in the two TS source files has an entry in `BIG_JS_METHODS`.
- Every `date-fns` function used in the two TS source files has an entry in `DATE_FNS_FUNCTIONS`.
- `tt_import_map.json` contains entries for all `@ghostfolio/` paths referenced in the two TS files.
- `pytest tt/tests/test_lib_map.py -v` passes.
- `make detect_rule_breaches` detects no hardcoded `@ghostfolio/` paths inside `tt/tt/` source files.

### Verification steps
- [ ] `pytest tt/tests/test_lib_map.py -v` — all tests pass
- [ ] `python -c "from tt.lib_map import BIG_JS_METHODS; print(BIG_JS_METHODS['plus'])"`
- [ ] `python -c "import json; m = json.load(open('tt/tt/scaffold/ghostfolio_pytx/tt_import_map.json')); print(len(m), 'entries')"`
- [ ] `make detect_rule_breaches` — output shows `detect_direct_mappings: PASS`

### Changelog entry (fill in on completion)
- **Completed:** —
- **What was done:** —
- **Deviations from plan:** —
- **Notes for next roadmap:** —

---

## Milestone 4 — Build the Python Code Generator

**Status:** [ ] Not started
**Agent:** Agent-Codegen
**Dependencies:** Milestone 1 (runner contract), Milestone 2 (parse tree schema), Milestone 3 (mapping tables)
**Scope:** `tt/tt/codegen.py` (new file only)
**Merge strategy:** New file; consumes `lib_map.py` (read-only) and the parse tree schema defined in M2 (read-only interface).

### Goal
Implement a code generator that takes a parse tree (produced by M2's `parse_ts_file`) and the mapping tables (from M3) and emits valid, PEP-8-compliant Python source code. The generator handles the mechanical transformation; correctness of the emitted Python is verified in M5.

### Tasks
- [ ] Implement `generate_python_class(class_node: dict, import_map: dict) -> str` that produces a complete Python class definition with all methods.
- [ ] Implement `generate_method(method_node: dict) -> str` that:
  - Converts camelCase method names to snake_case
  - Adds `self` as first parameter
  - Translates TypeScript parameter types using `TS_TYPE_MAP`
  - Translates method body lines (see below)
- [ ] Implement `translate_expression(ts_expr: str, context: dict) -> str` that handles:
  - `new Big(x)` → `Decimal(str(x))` (string constructor to avoid float imprecision)
  - `x.plus(y)` → `x + y`, `.minus` → `-`, `.times` → `*`, `.div` → `/`
  - `x.eq(y)` → `x == y`, `.gt` → `>`, `.lt` → `<`, `.gte` → `>=`, `.lte` → `<=`
  - `x.toNumber()` → `float(x)`, `x.toFixed(n)` → `f"{x:.{n}f}"`
  - `format(date, DATE_FORMAT)` → `date.strftime('%Y-%m-%d')`
  - `differenceInDays(a, b)` → `(a - b).days`
  - `eachDayOfInterval({start, end})` → generator using `timedelta`
  - `eachYearOfInterval({start, end})` → generator using `relativedelta`
  - `isBefore(a, b)` → `a < b`, `isAfter(a, b)` → `a > b`
  - `sortBy(arr, fn)` → `sorted(arr, key=fn)`
  - `cloneDeep(x)` → `copy.deepcopy(x)`
  - `?.` optional chaining → `x and x.y` pattern
  - Arrow functions `(x) => expr` → `lambda x: expr`
  - Template literals `` `text ${x}` `` → `f"text {x}"`
  - `Object.keys(x)` → `list(x.keys())`
  - `Object.entries(x)` → `list(x.items())`
  - `Array.from(x)` → `list(x)`
- [ ] Implement `generate_imports(used_libraries: list[str], import_map: dict) -> str` that produces the correct Python import block from `PYTHON_IMPORTS` and `tt_import_map.json`.
- [ ] Implement `camel_to_snake(name: str) -> str` utility.
- [ ] Write `tt/tests/test_codegen.py` testing each transformation with small inline inputs.

### Acceptance criteria
- `generate_python_class` produces syntactically valid Python (parseable by `ast.parse`).
- `camel_to_snake` correctly converts: `getSymbolMetrics` → `get_symbol_metrics`, `calculateOverallPerformance` → `calculate_overall_performance`, `getPerformanceCalculationType` → `get_performance_calculation_type`.
- `translate_expression` correctly converts `new Big(0).plus(new Big(1)).toNumber()` → valid Python evaluating to `1.0`.
- `pytest tt/tests/test_codegen.py -v` passes.
- Generated code passes `ast.parse()` on all test inputs.

### Verification steps
- [ ] `pytest tt/tests/test_codegen.py -v` — all tests pass
- [ ] `python -c "from tt.codegen import camel_to_snake; assert camel_to_snake('getSymbolMetrics') == 'get_symbol_metrics'"`
- [ ] `python -c "import ast; from tt.codegen import generate_python_class; ast.parse(generate_python_class({...}, {}))"`  (using a minimal class_node stub)
- [ ] `make detect_rule_breaches` — no new violations

### Changelog entry (fill in on completion)
- **Completed:** —
- **What was done:** —
- **Deviations from plan:** —
- **Notes for next roadmap:** —

---

## Milestone 5 — Translate RoaiPortfolioCalculator End-to-End

**Status:** [ ] Not started
**Agent:** Agent-Translator
**Dependencies:** Milestones 2, 3, 4
**Scope:** `tt/tt/translator.py` (rewrite), `tt/tt/cli.py` (minor update to wiring only)
**Merge strategy:** Replaces existing `translator.py` contents. `cli.py` change is additive (one import path update). M2/M3/M4 files are read-only inputs.

### Goal
Wire the parser (M2) → codegen (M4) pipeline into `translator.py` to produce a fully translated `RoaiPortfolioCalculator` that implements the abstract interface defined in `app/wrapper/portfolio/calculator/portfolio_calculator.py`. The translated calculator must produce correct chart history, investment timelines, holdings, dividends, and performance metrics — not stubs.

This is the core deliverable of the entire competition.

### Target interface (must be implemented correctly)
From `app/wrapper/portfolio/calculator/portfolio_calculator.py`:
- `get_performance() → dict` — must return `{chart: [...], firstOrderDate, performance: {...}}`
- `get_investments(group_by) → dict` — must return `{investments: [{date, investment}]}`
- `get_holdings() → dict` — must return `{holdings: {symbol: {...}}}`
- `get_details(base_currency) → dict`
- `get_dividends(group_by) → dict`
- `evaluate_report() → dict`

### Tasks
- [ ] Read `portfolio-calculator.ts` (parent) in full — understand: `getSnapshot`, `getChartData`, `getInvestments`, `getHoldings`, `getPerformance`, transaction point building, `getPortfolioSnapshot`.
- [ ] Read `portfolio-calculator.ts` (ROAI child) in full — understand: `getSymbolMetrics` (the largest method, handles per-symbol cost-basis, TWI, gross/net performance), `calculateOverallPerformance`, `getPerformanceCalculationType`.
- [ ] Rewrite `run_translation(repo_root, output_dir)` in `translator.py` to:
  1. Call `parse_ts_file()` on both TS source files.
  2. Call `generate_python_class()` on `RoaiPortfolioCalculator` and any helper methods from the parent class needed to make it work.
  3. Generate the required Python imports from `tt_import_map.json` + `PYTHON_IMPORTS`.
  4. Write the output to `output_dir/app/implementation/portfolio/calculator/roai/portfolio_calculator.py`.
- [ ] Ensure the generated file:
  - Imports `PortfolioCalculator` from `app.wrapper.portfolio.calculator.portfolio_calculator`
  - Imports `Decimal` from `decimal`
  - Imports `date`, `timedelta`, etc. from `datetime` / `dateutil`
  - Imports `copy` for `deepcopy`
  - Defines `class RoaiPortfolioCalculator(PortfolioCalculator):`
  - Implements all 6 abstract methods
- [ ] After generation, verify the output file passes `ast.parse()` (add this as an automated post-translation check inside `run_translation`).
- [ ] Manual inspection: read the generated file and verify the financial logic in `get_symbol_metrics` is semantically correct Python, not garbled output.
- [ ] Run `make translate-and-test-ghostfolio_pytx` and record how many tests pass. Target: materially more than the 48 baseline (scaffold-only) — aim for 80+.

### Key translation challenges to solve explicitly
- **Big.js chaining:** `new Big(0).plus(x).div(y)` must become `Decimal('0') + x / y` (or use Decimal arithmetic throughout).
- **`differenceInDays` direction:** TS `differenceInDays(a, b)` = `(a - b).days` in Python — order matters for sign.
- **`eachDayOfInterval({start, end})`** — TS destructures to named params; Python needs `date_range(start, end)` helper emitted inline.
- **Transaction point building loop** — large nested loop with accumulator variables; must translate cleanly without breaking indentation.
- **`SymbolProfile.symbol` pattern** — TS property access on nested object; Python dict access `act['SymbolProfile']['symbol']`.
- **`cloneDeep(this.activities.filter(...))`** — Python: `copy.deepcopy([a for a in self.activities if ...])`.

### Acceptance criteria
- Generated `portfolio_calculator.py` passes `ast.parse()` without error.
- `uv run --project tt tt translate` completes without error.
- `make translate-and-test-ghostfolio_pytx` runs to completion (server starts, tests run).
- Test result improves over 48 passed (scaffold-only baseline). Target ≥ 80 passed.
- `make detect_rule_breaches` passes all checks including `detect_explicit_implementation` and `detect_code_block_copying`.
- No `@ghostfolio/` string literals appear anywhere in `tt/tt/` (use `tt_import_map.json` exclusively).

### Verification steps
- [ ] `python -c "import ast; ast.parse(open('translations/ghostfolio_pytx/app/implementation/portfolio/calculator/roai/portfolio_calculator.py').read()); print('syntax ok')"`
- [ ] `uv run --project tt tt translate` exits 0
- [ ] `make translate-and-test-ghostfolio_pytx` — record X passed / Y failed
- [ ] `make detect_rule_breaches` — all checks PASS
- [ ] `python -c "from tt.codegen import camel_to_snake"` — still importable (no regression in M4)
- [ ] `pytest tt/tests/` — all unit tests from M2/M3/M4 still pass

### Changelog entry (fill in on completion)
- **Completed:** —
- **What was done:** —
- **Deviations from plan:** —
- **Notes for next roadmap:** —

---

## Milestone 6 — Iterate on Translation Quality

**Status:** [ ] Not started
**Agent:** Agent-Quality
**Dependencies:** Milestone 5
**Scope:** `tt/tt/translator.py`, `tt/tt/codegen.py`, `tt/tt/parser.py` — iterative fixes only. No new files.
**Merge strategy:** Modifications to existing files only. All changes are additive improvements; no breaking changes to the module interfaces established in M2–M4.

### Goal
Analyse failing API tests, trace each failure to a specific translation defect, and patch the parser/codegen/translator to fix it. Iterate until the test score is maximised and code quality metrics (`make scoring_codequality`) are acceptable.

### Tasks
- [ ] Run `make translate-and-test-ghostfolio_pytx` and collect the full list of failing test names.
- [ ] Group failures into categories:
  - Chart data missing or incorrect dates
  - Performance percentage calculation wrong
  - Holdings quantity or investment value wrong
  - Investments timeline grouping (month/year) wrong
  - Dividends/fees not tracked
  - xRay report structure wrong
- [ ] For each category, read the corresponding TypeScript logic and the generated Python, identify the translation bug, and fix it in `codegen.py` or `parser.py`.
- [ ] Re-run `uv run --project tt tt translate` after each fix to regenerate output; re-run tests to confirm improvement.
- [ ] Run `make scoring_codequality` on the generated `translations/ghostfolio_pytx/` — check `health_score`, `complexity_score`, `duplication_score`. Address any F-grade metrics.
- [ ] Run `make detect_rule_breaches` after every fix round — must stay clean.
- [ ] Commit after each meaningful improvement with a descriptive message.

### Acceptance criteria
- Test pass count is higher than M5 baseline; aim for maximum coverage achievable within competition time.
- `make detect_rule_breaches` passes all checks.
- `make scoring_codequality` shows no metric worse than D grade.
- Generated `portfolio_calculator.py` is readable, non-duplicative Python.

### Verification steps
- [ ] `make translate-and-test-ghostfolio_pytx` — record final X passed / Y failed
- [ ] `make evaluate_tt_ghostfolio` — record combined score
- [ ] `make detect_rule_breaches` — all PASS
- [ ] `make scoring_codequality` — review grades

### Changelog entry (fill in on completion)
- **Completed:** —
- **What was done:** —
- **Deviations from plan:** —
- **Notes for next roadmap:** —

---

## Milestone 7 — Complete SOLUTION.md and Publish Results

**Status:** [ ] Not started
**Agent:** Agent-Docs
**Dependencies:** Milestone 6
**Scope:** `SOLUTION.md` only
**Merge strategy:** Single file, no conflict risk.

### Goal
Write the mandatory `SOLUTION.md` explaining the architecture and coding approach in enough detail that judges can evaluate without needing to read source code. Also run `make publish_results` to post the final score to the live dashboard.

### Tasks
- [ ] Write the **Solution** section of `SOLUTION.md`:
  - Describe the four-module pipeline: parser → lib_map → codegen → translator
  - Explain what parse-tree nodes are produced and consumed
  - Describe the Big.js → Decimal translation strategy
  - Describe the date-fns → datetime translation strategy
  - Explain how `tt_import_map.json` avoids hardcoded project-specific paths in `tt/` core
  - Show a short before/after example: one TS snippet and the Python it produces
- [ ] Write the **Coding approach** section:
  - Describe the iterative workflow (translate → test → analyse failures → patch)
  - Note which milestones were done in parallel vs sequentially
  - Note any deviations from the roadmap
  - Reference the `/explain-tt-strategy` Claude Code skill for automated analysis
- [ ] Optionally add a simple ASCII diagram of the pipeline
- [ ] Run `make publish_results` to post the final evaluation to the leaderboard
- [ ] Confirm the commit that represents the final submission is on `main`

### Acceptance criteria
- `SOLUTION.md` covers both required sections (Solution + Coding approach).
- A judge reading `SOLUTION.md` alone can understand the pipeline without reading code.
- `make publish_results` completes without error.
- Final commit is on `main` before 18:30.

### Verification steps
- [ ] `cat SOLUTION.md` — both sections present and non-empty
- [ ] `make publish_results` — exits 0
- [ ] `git log --oneline -1` — HEAD is on `main` and commit log shows gradual development

### Changelog entry (fill in on completion)
- **Completed:** —
- **What was done:** —
- **Deviations from plan:** —
- **Notes for next roadmap:** —

---

## Dependency Graph

```
Milestone 1 (foundation — scaffold runner, tt_import_map.json, pyproject.toml)
├── Milestone 2 (parallel) — TypeScript Parser (parser.py)
├── Milestone 3 (parallel) — Library Mapping Tables (lib_map.py + tt_import_map.json populated)
└── (Milestone 4 waits for 2 + 3)

Milestone 2 + Milestone 3 → Milestone 4 (sequential)
  Milestone 4 — Python Code Generator (codegen.py)
  └── Milestone 5 (sequential)
        Milestone 5 — End-to-End Translation (translator.py rewrite)
        └── Milestone 6 (sequential)
              Milestone 6 — Iteration & Quality
              └── Milestone 7 (sequential)
                    Milestone 7 — SOLUTION.md + Publish
```

**Parallel execution windows:**
- M2 and M3 can run simultaneously once M1 is complete.
- M4 begins only after both M2 and M3 are done (it consumes both interfaces).
- M5–M7 are sequential (each depends on the previous).

**Critical path:** M1 → M2/M3 → M4 → M5 → M6 → M7

---

## Changelog

| Milestone | Title | Completed | Summary |
|-----------|-------|-----------|---------|
| M1 | Establish Project Scaffold and Runner Infrastructure | — | — |
| M2 | Build the TypeScript Parser | — | — |
| M3 | Build the Library Mapping Tables | — | — |
| M4 | Build the Python Code Generator | — | — |
| M5 | Translate RoaiPortfolioCalculator End-to-End | — | — |
| M6 | Iterate on Translation Quality | — | — |
| M7 | Complete SOLUTION.md and Publish Results | — | — |
