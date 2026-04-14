"""Library mapping tables for the Ghostfolio calculator translation.

This module is pure data. Branch A's translator/codegen consumes these tables
to translate the two Ghostfolio calculator TypeScript files without hardcoding
library-specific behavior elsewhere.
"""
from __future__ import annotations

# Big.js method names used in the Ghostfolio calculator sources.
# Arithmetic methods map to Python operators; comparison helpers map to
# comparison operators; `mul` is a source alias for multiplication.
BIG_JS_METHODS: dict[str, str] = {
    "abs": "abs",
    "div": "/",
    "eq": "==",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "minus": "-",
    "mod": "%",
    "mul": "*",
    "plus": "+",
    "pow": "**",
    "sqrt": "sqrt",
    "times": "*",
    "toFixed": "quantize",
    "toNumber": "float",
}

# date-fns functions used by the calculator sources.
# Some map to operators or named Python helpers rather than 1:1 functions.
DATE_FNS_FUNCTIONS: dict[str, str] = {
    "addMilliseconds": "add_ms",
    "differenceInDays": "days_diff",
    "eachDayOfInterval": "each_day",
    "eachYearOfInterval": "each_year",
    "endOfDay": "end_of_day",
    "endOfYear": "end_of_year",
    "format": "strftime",
    "isAfter": ">",
    "isBefore": "<",
    "isThisYear": "is_this_year",
    "isWithinInterval": "within",
    "min": "min",
    "startOfDay": "start_of_day",
    "startOfYear": "start_of_year",
    "subDays": "sub_days",
}

# lodash functions used by the calculator sources.
LODASH_FUNCTIONS: dict[str, str] = {
    "cloneDeep": "deepcopy",
    "isNumber": "is_number",
    "sortBy": "sorted_by",
    "sum": "sum",
    "uniqBy": "uniq_by",
}

# TypeScript type names encountered in the two calculator source files.
# Primitive names map directly; project-specific interfaces and models map to
# their Python wrapper class names or plain dict-based representations.
TS_TYPE_MAP: dict[str, str] = {
    "Activity": "dict[str, Any]",
    "AssetProfileIdentifier": "dict[str, Any]",
    "AssetSubClass": "str",
    "Big": "Decimal",
    "ConfigurationService": "Any",
    "CurrentRateService": "CurrentRateService",
    "DataGatheringItem": "dict[str, Any]",
    "DataProviderInfo": "dict[str, Any]",
    "Date": "date",
    "DateRange": "str",
    "ExchangeRateDataService": "Any",
    "Filter": "dict[str, Any]",
    "GroupBy": "str",
    "HistoricalDataItem": "dict[str, Any]",
    "InvestmentItem": "dict[str, Any]",
    "Logger": "Any",
    "PerformanceCalculationType": "str",
    "PortfolioOrder": "PortfolioOrder",
    "PortfolioOrderItem": "PortfolioOrderItem",
    "PortfolioSnapshot": "dict[str, Any]",
    "PortfolioSnapshotValue": "dict[str, Any]",
    "RedisCacheService": "Any",
    "Record": "dict[str, Any]",
    "ResponseError": "dict[str, Any]",
    "SymbolMetrics": "SymbolMetrics",
    "TimelinePosition": "dict[str, Any]",
    "TransactionPoint": "dict[str, Any]",
    "TransactionPointSymbol": "TransactionPointSymbol",
    "Array": "list",
    "Promise": "Awaitable",
    "any": "Any",
    "boolean": "bool",
    "never": "NoReturn",
    "null": "None",
    "number": "float",
    "string": "str",
    "undefined": "None",
    "void": "None",
}

# Python imports grouped by the capability the generator needs.
PYTHON_IMPORTS: dict[str, list[str]] = {
    "copy": ["import copy"],
    "dateutil": ["from dateutil.relativedelta import relativedelta"],
    "datetime": ["from datetime import date, datetime, timedelta"],
    "decimal": ["from decimal import Decimal, ROUND_HALF_UP"],
    "typing": ["from typing import Any, Awaitable, NoReturn, Optional"],
}
