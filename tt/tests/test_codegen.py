from __future__ import annotations

from tt.codegen import (
    camel_to_snake,
    generate_helper_functions,
    generate_imports,
    generate_python_class,
    translate_expression,
)


def test_camel_to_snake_handles_mixed_caps() -> None:
    assert camel_to_snake("getSymbolMetrics") == "get_symbol_metrics"
    assert camel_to_snake("getROAI") == "get_roai"


def test_translate_expression_handles_common_patterns() -> None:
    assert translate_expression("this.value.plus(new Big(1));") == "(self.value + Decimal(str(1)))"
    assert translate_expression("format(date, DATE_FORMAT)") == "date.strftime('%Y-%m-%d')"
    assert "copy.deepcopy" in translate_expression("cloneDeep(items)")


def test_generate_imports_deduplicates_and_includes_basic_imports() -> None:
    rendered = generate_imports(["decimal", "decimal"], {})
    assert "from __future__ import annotations" in rendered
    assert "from typing import Any" in rendered
    assert rendered.count("from decimal import Decimal") == 1


def test_generate_python_class_renders_valid_structure() -> None:
    class_node = {
        "name": "SampleCalculator",
        "base_class": "PortfolioCalculator",
        "properties": [{"name": "chartDates", "ts_type": "Array<string>", "visibility": "private", "is_static": False}],
        "methods": [
            {
                "name": "getPerformanceCalculationType",
                "visibility": "protected",
                "params": [],
                "return_type": "string",
                "body_lines": ["return PerformanceCalculationType.ROAI;"],
            }
        ],
    }
    rendered = generate_python_class(class_node, {})
    assert "class SampleCalculator(PortfolioCalculator):" in rendered
    assert "chart_dates: list[str] = None" in rendered
    assert "def get_performance_calculation_type(self) -> str:" in rendered


def test_generate_helper_functions_contains_interval_helpers() -> None:
    helpers = generate_helper_functions()
    assert "def each_day_of_interval" in helpers
    assert "def each_year_of_interval" in helpers
