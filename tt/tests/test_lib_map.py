from __future__ import annotations

import json
from pathlib import Path

from tt.lib_map import (
    BIG_JS_METHODS,
    DATE_FNS_FUNCTIONS,
    LODASH_FUNCTIONS,
    PYTHON_IMPORTS,
    TS_TYPE_MAP,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMPORT_MAP_PATH = PROJECT_ROOT / "tt" / "scaffold" / "ghostfolio_pytx" / "tt_import_map.json"

EXPECTED_IMPORT_MAP_KEYS = {
    "@ghostfolio/api/app/portfolio/calculator/portfolio-calculator",
    "@ghostfolio/api/app/portfolio/current-rate.service",
    "@ghostfolio/api/app/portfolio/interfaces/portfolio-order.interface",
    "@ghostfolio/api/app/portfolio/interfaces/portfolio-order-item.interface",
    "@ghostfolio/api/app/portfolio/interfaces/snapshot-value.interface",
    "@ghostfolio/api/app/portfolio/interfaces/transaction-point.interface",
    "@ghostfolio/api/app/portfolio/interfaces/transaction-point-symbol.interface",
    "@ghostfolio/api/app/redis-cache/redis-cache.service",
    "@ghostfolio/api/helper/portfolio.helper",
    "@ghostfolio/api/interceptors/performance-logging/performance-logging.interceptor",
    "@ghostfolio/api/services/configuration/configuration.service",
    "@ghostfolio/api/services/exchange-rate-data/exchange-rate-data.service",
    "@ghostfolio/api/services/interfaces/interfaces",
    "@ghostfolio/api/services/queues/portfolio-snapshot/portfolio-snapshot.service",
    "@ghostfolio/common/calculation-helper",
    "@ghostfolio/common/config",
    "@ghostfolio/common/helper",
    "@ghostfolio/common/interfaces",
    "@ghostfolio/common/models",
    "@ghostfolio/common/types",
    "@ghostfolio/common/types/performance-calculation-type.type",
}


def test_mapping_tables_are_populated_and_spot_checked() -> None:
    assert BIG_JS_METHODS["plus"] == "+"
    assert BIG_JS_METHODS["mul"] == "*"
    assert DATE_FNS_FUNCTIONS["isBefore"] == "<"
    assert DATE_FNS_FUNCTIONS["addMilliseconds"] == "add_ms"
    assert LODASH_FUNCTIONS["cloneDeep"] == "deepcopy"
    assert LODASH_FUNCTIONS["sortBy"] == "sorted_by"
    assert TS_TYPE_MAP["Big"] == "Decimal"
    assert TS_TYPE_MAP["Date"] == "date"
    assert all(mapping for mapping in (BIG_JS_METHODS, DATE_FNS_FUNCTIONS, LODASH_FUNCTIONS, TS_TYPE_MAP, PYTHON_IMPORTS))
    assert any("Decimal" in line for line in PYTHON_IMPORTS["decimal"])


def test_import_map_json_loads_and_matches_expected_paths() -> None:
    import_map = json.loads(IMPORT_MAP_PATH.read_text(encoding="utf-8"))

    assert len(import_map) == len(EXPECTED_IMPORT_MAP_KEYS)
    assert set(import_map) == EXPECTED_IMPORT_MAP_KEYS
    assert (
        import_map["@ghostfolio/api/app/portfolio/calculator/portfolio-calculator"]
        == "app.wrapper.portfolio.calculator.portfolio_calculator"
    )
    assert import_map["@ghostfolio/common/interfaces"] == "app.wrapper.portfolio.interfaces"
    assert (
        import_map["@ghostfolio/api/app/portfolio/interfaces/portfolio-order-item.interface"]
        == "app.wrapper.portfolio.interfaces.portfolio_order_item"
    )
