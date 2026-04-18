from __future__ import annotations

from app.wrapper.portfolio.calculator.portfolio_calculator import PortfolioCalculator
from app.wrapper.portfolio.interfaces.portfolio_order_item import PortfolioOrderItem
class RoaiPortfolioCalculator(PortfolioCalculator):
    chart_dates: object = None

    def calculate_overall_performance(self, positions):
        pass
        # body exceeds translator cap (2 stmts) — stubbed

    def get_performance_calculation_type(self):
        return PerformanceCalculationType.ROAI

    def get_symbol_metrics(self, _kw):
        pass
        # body exceeds translator cap (2 stmts) — stubbed

