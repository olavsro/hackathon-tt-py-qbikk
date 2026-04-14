class RoaiPortfolioCalculator(PortfolioCalculator):
    def __init__(self, activities, current_rate_service):
        super().__init__(activities, current_rate_service)
        self.chart_dates = None
        self._transaction_points = []
        self._compute_transaction_points()
