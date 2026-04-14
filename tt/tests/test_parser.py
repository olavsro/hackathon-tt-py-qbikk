from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from tt.parser import extract_class_methods, parse_ts_file


def _parse_inline(tmp_path: Path, source: str):
    path = tmp_path / "snippet.ts"
    path.write_text(dedent(source).strip() + "\n", encoding="utf-8")
    return parse_ts_file(path)


def test_parse_imports_classes_properties_and_methods(tmp_path: Path) -> None:
    tree = _parse_inline(
        tmp_path,
        """
        import {
          Big,
          cloneDeep,
          sortBy
        } from 'big.js';
        import { PortfolioCalculator } from '@ghostfolio/api/app/portfolio/calculator/portfolio-calculator';

        export class Foo extends Bar {
          private chartDates: string[];
          protected static readonly ENABLE_LOGGING = false;

          protected calculateOverallPerformance(
            positions: TimelinePosition[]
          ): PortfolioSnapshot {
            const nextValue = this.snapshot?.value ?? 0;
            const buildLabel = (count: number) => `count: ${count}`;
            if (nextValue > 0) {
              return { value: nextValue, label: buildLabel(nextValue) };
            } else {
              return {
                value: 0,
                label: buildLabel(0)
              };
            }
          }

          protected abstract getPerformanceCalculationType(): string;
        }
        """,
    )

    assert tree["imports"] == [
        {
            "symbols": ["Big", "cloneDeep", "sortBy"],
            "module": "big.js",
        },
        {
            "symbols": ["PortfolioCalculator"],
            "module": "@ghostfolio/api/app/portfolio/calculator/portfolio-calculator",
        },
    ]

    class_node = tree["classes"][0]
    assert class_node["name"] == "Foo"
    assert class_node["base_class"] == "Bar"
    assert [prop["name"] for prop in class_node["properties"]] == [
        "chartDates",
        "ENABLE_LOGGING",
    ]
    assert class_node["properties"][0]["ts_type"] == "string[]"
    assert class_node["properties"][1]["is_static"] is True

    methods = extract_class_methods(tree, "Foo")
    assert [method["name"] for method in methods] == [
        "calculateOverallPerformance",
        "getPerformanceCalculationType",
    ]

    performance_method = methods[0]
    assert performance_method["visibility"] == "protected"
    assert performance_method["params"] == [
        {"name": "positions", "ts_type": "TimelinePosition[]"}
    ]
    assert performance_method["return_type"] == "PortfolioSnapshot"
    assert any(
        line.strip() == "const nextValue = this.snapshot?.value ?? 0;"
        for line in performance_method["body_lines"]
    )
    assert any(
        line.strip() == "const buildLabel = (count: number) => `count: ${count}`;"
        for line in performance_method["body_lines"]
    )
    assert performance_method["body_lines"][-1].strip() == "}"


def test_parse_top_level_const_and_abstract_method(tmp_path: Path) -> None:
    tree = _parse_inline(
        tmp_path,
        """
        const x: Big = new Big(0);
        const y = new Big(1);

        export abstract class Example {
          protected abstract getPerformanceCalculationType(): string;
        }
        """,
    )

    assert tree["top_level_vars"] == [
        {
            "name": "x",
            "ts_type": "Big",
            "initializer": "new Big(0)",
        },
        {
            "name": "y",
            "ts_type": "",
            "initializer": "new Big(1)",
        },
    ]

    methods = extract_class_methods(tree, "Example")
    assert methods == [
        {
            "name": "getPerformanceCalculationType",
            "visibility": "protected",
            "params": [],
            "return_type": "string",
            "body_lines": [],
        }
    ]


def test_method_body_handles_nested_braces_and_arrow_functions(tmp_path: Path) -> None:
    tree = _parse_inline(
        tmp_path,
        """
        export class Nested extends Base {
          public run(value: number): number {
            const fallback = this.cache?.items?.[0] ?? { count: 1 };
            const formatter = (count: number) => `count: ${count}`;
            if (fallback.count > 0) {
              for (const item of [1, 2, 3]) {
                if (item > 1) {
                  return formatter(item).length;
                }
              }
            } else {
              return 0;
            }
            return value;
          }
        }
        """,
    )

    method = extract_class_methods(tree, "Nested")[0]
    assert method["body_lines"][0].strip() == "const fallback = this.cache?.items?.[0] ?? { count: 1 };"
    assert any(
        line.strip() == "const formatter = (count: number) => `count: ${count}`;"
        for line in method["body_lines"]
    )
    assert any(
        line.strip() == "for (const item of [1, 2, 3]) {"
        for line in method["body_lines"]
    )
    assert method["body_lines"][-1].strip() == "return value;"


def test_real_ghostfolio_calculator_files_parse() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    roai_tree = parse_ts_file(
        repo_root
        / "projects"
        / "ghostfolio"
        / "apps"
        / "api"
        / "src"
        / "app"
        / "portfolio"
        / "calculator"
        / "roai"
        / "portfolio-calculator.ts"
    )
    parent_tree = parse_ts_file(
        repo_root
        / "projects"
        / "ghostfolio"
        / "apps"
        / "api"
        / "src"
        / "app"
        / "portfolio"
        / "calculator"
        / "portfolio-calculator.ts"
    )

    assert [class_node["name"] for class_node in roai_tree["classes"]] == [
        "RoaiPortfolioCalculator"
    ]
    assert [class_node["name"] for class_node in parent_tree["classes"]] == [
        "PortfolioCalculator"
    ]

    roai_methods = {method["name"] for method in extract_class_methods(roai_tree, "RoaiPortfolioCalculator")}
    parent_methods = {method["name"] for method in extract_class_methods(parent_tree, "PortfolioCalculator")}

    assert {"calculateOverallPerformance", "getPerformanceCalculationType", "getSymbolMetrics"} <= roai_methods
    assert {"getInvestments", "getInvestmentsByGroup", "getPerformance"} <= parent_methods
