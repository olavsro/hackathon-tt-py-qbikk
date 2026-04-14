    def get_holdings(self) -> dict:
        # Method not present in TypeScript calculator; returns stub
        return {"holdings": {}}

    def get_details(self, base_currency: str = "USD") -> dict:
        return {"accounts": {}, "holdings": {}, "summary": {}, "hasError": False}

    def get_dividends(self, group_by=None) -> dict:
        return {"dividends": []}

    def evaluate_report(self) -> dict:
        return {"xRay": {"categories": [], "statistics": {"rulesActiveCount": 0, "rulesFulfilledCount": 0}}}
