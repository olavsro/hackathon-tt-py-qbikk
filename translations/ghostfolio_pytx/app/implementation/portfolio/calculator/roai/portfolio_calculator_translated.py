from __future__ import annotations

from app.wrapper.portfolio.calculator.portfolio_calculator import PortfolioCalculator
from app.wrapper.portfolio.interfaces.portfolio_order_item import PortfolioOrderItem
class RoaiPortfolioCalculator(PortfolioCalculator):
    chart_dates: object = None

    def calculate_overall_performance(self, positions):
        currentValueInBaseCurrency = Big(0)
        grossPerformance = Big(0)
        grossPerformanceWithCurrencyEffect = Big(0)
        hasErrors = False
        netPerformance = Big(0)
        totalFeesWithCurrencyEffect = Big(0)
        totalInterestWithCurrencyEffect = Big(0)
        totalInvestment = Big(0)
        totalInvestmentWithCurrencyEffect = Big(0)
        totalTimeWeightedInvestment = Big(0)
        totalTimeWeightedInvestmentWithCurrencyEffect = Big(0)
        for currentPosition in positions.filter((lambda _kw: includeInTotalAssetValue)):
            if (currentPosition.fee_in_base_currency):
                totalFeesWithCurrencyEffect = totalFeesWithCurrencyEffect.plus(currentPosition.fee_in_base_currency)
            if (currentPosition.value_in_base_currency):
                currentValueInBaseCurrency = currentValueInBaseCurrency.plus(currentPosition.value_in_base_currency)
            else:
                hasErrors = True
            if (currentPosition.investment):
                totalInvestment = totalInvestment.plus(currentPosition.investment)
                totalInvestmentWithCurrencyEffect = totalInvestmentWithCurrencyEffect.plus(currentPosition.investment_with_currency_effect)
            else:
                hasErrors = True
            if (currentPosition.gross_performance):
                grossPerformance = grossPerformance.plus(currentPosition.gross_performance)
                grossPerformanceWithCurrencyEffect = grossPerformanceWithCurrencyEffect.plus(currentPosition.gross_performance_with_currency_effect)
                netPerformance = netPerformance.plus(currentPosition.net_performance)
            elif ((not currentPosition.quantity.eq(0))):
                hasErrors = True
            if (currentPosition.time_weighted_investment):
                totalTimeWeightedInvestment = totalTimeWeightedInvestment.plus(currentPosition.time_weighted_investment)
                totalTimeWeightedInvestmentWithCurrencyEffect = totalTimeWeightedInvestmentWithCurrencyEffect.plus(currentPosition.time_weighted_investment_with_currency_effect)
            elif ((not currentPosition.quantity.eq(0))):
                Logger.warn(f'Missing historical market data for {currentPosition.symbol} ({currentPosition.data_source})', 'PortfolioCalculator')
                hasErrors = True
        return {'currentValueInBaseCurrency': currentValueInBaseCurrency, 'hasErrors': hasErrors, 'positions': positions, 'totalFeesWithCurrencyEffect': totalFeesWithCurrencyEffect, 'totalInterestWithCurrencyEffect': totalInterestWithCurrencyEffect, 'totalInvestment': totalInvestment, 'totalInvestmentWithCurrencyEffect': totalInvestmentWithCurrencyEffect, 'activitiesCount': self.activities.filter((lambda _kw: (type in ['BUY', 'SELL']))).length, 'createdAt': Date(), 'errors': [], 'historicalData': [], 'totalLiabilitiesWithCurrencyEffect': Big(0)}

    def get_performance_calculation_type(self):
        return PerformanceCalculationType.ROAI

    def get_symbol_metrics(self, _kw):
        currentExchangeRate = exchangeRates[format(Date(), DATE_FORMAT)]
        currentValues = {}
        currentValuesWithCurrencyEffect = {}
        fees = Big(0)
        feesAtStartDate = Big(0)
        feesAtStartDateWithCurrencyEffect = Big(0)
        feesWithCurrencyEffect = Big(0)
        grossPerformance = Big(0)
        grossPerformanceWithCurrencyEffect = Big(0)
        grossPerformanceAtStartDate = Big(0)
        grossPerformanceAtStartDateWithCurrencyEffect = Big(0)
        grossPerformanceFromSells = Big(0)
        grossPerformanceFromSellsWithCurrencyEffect = Big(0)
        initialValue = None
        initialValueWithCurrencyEffect = None
        investmentAtStartDate = None
        investmentAtStartDateWithCurrencyEffect = None
        investmentValuesAccumulated = {}
        investmentValuesAccumulatedWithCurrencyEffect = {}
        investmentValuesWithCurrencyEffect = {}
        lastAveragePrice = Big(0)
        lastAveragePriceWithCurrencyEffect = Big(0)
        netPerformanceValues = {}
        netPerformanceValuesWithCurrencyEffect = {}
        timeWeightedInvestmentValues = {}
        timeWeightedInvestmentValuesWithCurrencyEffect = {}
        totalAccountBalanceInBaseCurrency = Big(0)
        totalDividend = Big(0)
        totalDividendInBaseCurrency = Big(0)
        totalInterest = Big(0)
        totalInterestInBaseCurrency = Big(0)
        totalInvestment = Big(0)
        totalInvestmentFromBuyTransactions = Big(0)
        totalInvestmentFromBuyTransactionsWithCurrencyEffect = Big(0)
        totalInvestmentWithCurrencyEffect = Big(0)
        totalLiabilities = Big(0)
        totalLiabilitiesInBaseCurrency = Big(0)
        totalQuantityFromBuyTransactions = Big(0)
        totalUnits = Big(0)
        valueAtStartDate = None
        valueAtStartDateWithCurrencyEffect = None
        # Clone orders to keep the original values in this.orders
        orders = cloneDeep(self.activities.filter((lambda _kw: (SymbolProfile.symbol == symbol))))
        isCash = (orders[0].symbol_profile.asset_sub_class == 'CASH')
        if ((orders.length <= 0)):
            return {'currentValues': {}, 'currentValuesWithCurrencyEffect': {}, 'feesWithCurrencyEffect': Big(0), 'grossPerformance': Big(0), 'grossPerformancePercentage': Big(0), 'grossPerformancePercentageWithCurrencyEffect': Big(0), 'grossPerformanceWithCurrencyEffect': Big(0), 'hasErrors': False, 'initialValue': Big(0), 'initialValueWithCurrencyEffect': Big(0), 'investmentValuesAccumulated': {}, 'investmentValuesAccumulatedWithCurrencyEffect': {}, 'investmentValuesWithCurrencyEffect': {}, 'netPerformance': Big(0), 'netPerformancePercentage': Big(0), 'netPerformancePercentageWithCurrencyEffectMap': {}, 'netPerformanceValues': {}, 'netPerformanceValuesWithCurrencyEffect': {}, 'netPerformanceWithCurrencyEffectMap': {}, 'timeWeightedInvestment': Big(0), 'timeWeightedInvestmentValues': {}, 'timeWeightedInvestmentValuesWithCurrencyEffect': {}, 'timeWeightedInvestmentWithCurrencyEffect': Big(0), 'totalAccountBalanceInBaseCurrency': Big(0), 'totalDividend': Big(0), 'totalDividendInBaseCurrency': Big(0), 'totalInterest': Big(0), 'totalInterestInBaseCurrency': Big(0), 'totalInvestment': Big(0), 'totalInvestmentWithCurrencyEffect': Big(0), 'totalLiabilities': Big(0), 'totalLiabilitiesInBaseCurrency': Big(0)}
        dateOfFirstTransaction = Date(orders[0].date)
        endDateString = format(end, DATE_FORMAT)
        startDateString = format(start, DATE_FORMAT)
        unitPriceAtStartDate = marketSymbolMap[startDateString][symbol]
        unitPriceAtEndDate = marketSymbolMap[endDateString][symbol]
        latestActivity = orders.at((-1))
        if (((((dataSource == 'MANUAL') and (latestActivity.type in ['BUY', 'SELL'])) and latestActivity.unit_price) and (not unitPriceAtEndDate))):
            # For BUY / SELL activities with a MANUAL data source where no historical market price is available,
            # the calculation should fall back to using the activity’s unit price.
            unitPriceAtEndDate = latestActivity.unit_price
        elif (isCash):
            unitPriceAtEndDate = Big(1)
        if (((not unitPriceAtEndDate) or (((not unitPriceAtStartDate) and isBefore(dateOfFirstTransaction, start))))):
            return {'currentValues': {}, 'currentValuesWithCurrencyEffect': {}, 'feesWithCurrencyEffect': Big(0), 'grossPerformance': Big(0), 'grossPerformancePercentage': Big(0), 'grossPerformancePercentageWithCurrencyEffect': Big(0), 'grossPerformanceWithCurrencyEffect': Big(0), 'hasErrors': True, 'initialValue': Big(0), 'initialValueWithCurrencyEffect': Big(0), 'investmentValuesAccumulated': {}, 'investmentValuesAccumulatedWithCurrencyEffect': {}, 'investmentValuesWithCurrencyEffect': {}, 'netPerformance': Big(0), 'netPerformancePercentage': Big(0), 'netPerformancePercentageWithCurrencyEffectMap': {}, 'netPerformanceWithCurrencyEffectMap': {}, 'netPerformanceValues': {}, 'netPerformanceValuesWithCurrencyEffect': {}, 'timeWeightedInvestment': Big(0), 'timeWeightedInvestmentValues': {}, 'timeWeightedInvestmentValuesWithCurrencyEffect': {}, 'timeWeightedInvestmentWithCurrencyEffect': Big(0), 'totalAccountBalanceInBaseCurrency': Big(0), 'totalDividend': Big(0), 'totalDividendInBaseCurrency': Big(0), 'totalInterest': Big(0), 'totalInterestInBaseCurrency': Big(0), 'totalInvestment': Big(0), 'totalInvestmentWithCurrencyEffect': Big(0), 'totalLiabilities': Big(0), 'totalLiabilitiesInBaseCurrency': Big(0)}
        # Add a synthetic order at the start and the end date
        orders.append({'date': startDateString, 'fee': Big(0), 'feeInBaseCurrency': Big(0), 'itemType': 'start', 'quantity': Big(0), 'SymbolProfile': {'dataSource': dataSource, 'symbol': symbol, 'assetSubClass': ('CASH' if isCash else None)}, 'type': 'BUY', 'unitPrice': unitPriceAtStartDate})
        orders.append({'date': endDateString, 'fee': Big(0), 'feeInBaseCurrency': Big(0), 'itemType': 'end', 'SymbolProfile': {'dataSource': dataSource, 'symbol': symbol, 'assetSubClass': ('CASH' if isCash else None)}, 'quantity': Big(0), 'type': 'BUY', 'unitPrice': unitPriceAtEndDate})
        lastUnitPrice = None
        ordersByDate = {}
        for order in orders:
            ordersByDate[order.date] = (ordersByDate[order.date] if ordersByDate[order.date] is not None else [])
            ordersByDate[order.date].append(order)
        if ((not self.chart_dates)):
            self.chart_dates = Object.keys(chartDateMap).sort()
        for dateString in self.chart_dates:
            if ((dateString < startDateString)):
                continue
            elif ((dateString > endDateString)):
                break
            if ((ordersByDate[dateString].length > 0)):
                for order in ordersByDate[dateString]:
                    order.unit_price_from_market_data = (marketSymbolMap[dateString][symbol] if marketSymbolMap[dateString][symbol] is not None else lastUnitPrice)
            else:
                orders.append({'date': dateString, 'fee': Big(0), 'feeInBaseCurrency': Big(0), 'quantity': Big(0), 'SymbolProfile': {'dataSource': dataSource, 'symbol': symbol, 'assetSubClass': ('CASH' if isCash else None)}, 'type': 'BUY', 'unitPrice': (marketSymbolMap[dateString][symbol] if marketSymbolMap[dateString][symbol] is not None else lastUnitPrice), 'unitPriceFromMarketData': (marketSymbolMap[dateString][symbol] if marketSymbolMap[dateString][symbol] is not None else lastUnitPrice)})
            latestActivity = orders.at((-1))
            lastUnitPrice = (latestActivity.unit_price_from_market_data if latestActivity.unit_price_from_market_data is not None else latestActivity.unit_price)
        # Sort orders so that the start and end placeholder order are at the correct
        # position
        orders = sortBy(orders, (lambda _kw: True))
        indexOfStartOrder = orders.find_index((lambda _kw: (itemType == 'start')))
        indexOfEndOrder = orders.find_index((lambda _kw: (itemType == 'end')))
        totalInvestmentDays = 0
        sumOfTimeWeightedInvestments = Big(0)
        sumOfTimeWeightedInvestmentsWithCurrencyEffect = Big(0)
        i = 0
        while (i < orders.length):
            order = orders[i]
            if (PortfolioCalculator.ENABLE_LOGGING):
                console.log()
                console.log()
                console.log((i + 1), order.date, order.type, (f'({order.item_type})' if order.item_type else ''))
            exchangeRateAtOrderDate = exchangeRates[order.date]
            if ((order.type == 'DIVIDEND')):
                dividend = order.quantity.mul(order.unit_price)
                totalDividend = totalDividend.plus(dividend)
                totalDividendInBaseCurrency = totalDividendInBaseCurrency.plus(dividend.mul((exchangeRateAtOrderDate if exchangeRateAtOrderDate is not None else 1)))
            elif ((order.type == 'INTEREST')):
                interest = order.quantity.mul(order.unit_price)
                totalInterest = totalInterest.plus(interest)
                totalInterestInBaseCurrency = totalInterestInBaseCurrency.plus(interest.mul((exchangeRateAtOrderDate if exchangeRateAtOrderDate is not None else 1)))
            elif ((order.type == 'LIABILITY')):
                liabilities = order.quantity.mul(order.unit_price)
                totalLiabilities = totalLiabilities.plus(liabilities)
                totalLiabilitiesInBaseCurrency = totalLiabilitiesInBaseCurrency.plus(liabilities.mul((exchangeRateAtOrderDate if exchangeRateAtOrderDate is not None else 1)))
            if ((order.item_type == 'start')):
                # Take the unit price of the order as the market price if there are no
                # orders of this symbol before the start date
                order.unit_price = (orders[(i + 1)].unit_price if (indexOfStartOrder == 0) else unitPriceAtStartDate)
            if (order.fee):
                order.fee_in_base_currency = order.fee.mul((currentExchangeRate if currentExchangeRate is not None else 1))
                order.fee_in_base_currency_with_currency_effect = order.fee.mul((exchangeRateAtOrderDate if exchangeRateAtOrderDate is not None else 1))
            unitPrice = (order.unit_price if (order.type in ['BUY', 'SELL']) else order.unit_price_from_market_data)
            if (unitPrice):
                order.unit_price_in_base_currency = unitPrice.mul((currentExchangeRate if currentExchangeRate is not None else 1))
                order.unit_price_in_base_currency_with_currency_effect = unitPrice.mul((exchangeRateAtOrderDate if exchangeRateAtOrderDate is not None else 1))
            marketPriceInBaseCurrency = (order.unit_price_from_market_data.mul((currentExchangeRate if currentExchangeRate is not None else 1)) if order.unit_price_from_market_data.mul((currentExchangeRate if currentExchangeRate is not None else 1)) is not None else Big(0))
            marketPriceInBaseCurrencyWithCurrencyEffect = (order.unit_price_from_market_data.mul((exchangeRateAtOrderDate if exchangeRateAtOrderDate is not None else 1)) if order.unit_price_from_market_data.mul((exchangeRateAtOrderDate if exchangeRateAtOrderDate is not None else 1)) is not None else Big(0))
            valueOfInvestmentBeforeTransaction = totalUnits.mul(marketPriceInBaseCurrency)
            valueOfInvestmentBeforeTransactionWithCurrencyEffect = totalUnits.mul(marketPriceInBaseCurrencyWithCurrencyEffect)
            if (((not investmentAtStartDate) and (i >= indexOfStartOrder))):
                investmentAtStartDate = (totalInvestment if totalInvestment is not None else Big(0))
                investmentAtStartDateWithCurrencyEffect = (totalInvestmentWithCurrencyEffect if totalInvestmentWithCurrencyEffect is not None else Big(0))
                valueAtStartDate = valueOfInvestmentBeforeTransaction
                valueAtStartDateWithCurrencyEffect = valueOfInvestmentBeforeTransactionWithCurrencyEffect
            transactionInvestment = Big(0)
            transactionInvestmentWithCurrencyEffect = Big(0)
            if ((order.type == 'BUY')):
                transactionInvestment = order.quantity.mul(order.unit_price_in_base_currency).mul(getFactor(order.type))
                transactionInvestmentWithCurrencyEffect = order.quantity.mul(order.unit_price_in_base_currency_with_currency_effect).mul(getFactor(order.type))
                totalQuantityFromBuyTransactions = totalQuantityFromBuyTransactions.plus(order.quantity)
                totalInvestmentFromBuyTransactions = totalInvestmentFromBuyTransactions.plus(transactionInvestment)
                totalInvestmentFromBuyTransactionsWithCurrencyEffect = totalInvestmentFromBuyTransactionsWithCurrencyEffect.plus(transactionInvestmentWithCurrencyEffect)
            elif ((order.type == 'SELL')):
                if (totalUnits.gt(0)):
                    transactionInvestment = totalInvestment.div(totalUnits).mul(order.quantity).mul(getFactor(order.type))
                    transactionInvestmentWithCurrencyEffect = totalInvestmentWithCurrencyEffect.div(totalUnits).mul(order.quantity).mul(getFactor(order.type))
            if (PortfolioCalculator.ENABLE_LOGGING):
                console.log('order.quantity', order.quantity.to_number())
                console.log('transactionInvestment', transactionInvestment.to_number())
                console.log('transactionInvestmentWithCurrencyEffect', transactionInvestmentWithCurrencyEffect.to_number())
            totalInvestmentBeforeTransaction = totalInvestment
            totalInvestmentBeforeTransactionWithCurrencyEffect = totalInvestmentWithCurrencyEffect
            totalInvestment = totalInvestment.plus(transactionInvestment)
            totalInvestmentWithCurrencyEffect = totalInvestmentWithCurrencyEffect.plus(transactionInvestmentWithCurrencyEffect)
            if (((i >= indexOfStartOrder) and (not initialValue))):
                if (((i == indexOfStartOrder) and (not valueOfInvestmentBeforeTransaction.eq(0)))):
                    initialValue = valueOfInvestmentBeforeTransaction
                    initialValueWithCurrencyEffect = valueOfInvestmentBeforeTransactionWithCurrencyEffect
                elif (transactionInvestment.gt(0)):
                    initialValue = transactionInvestment
                    initialValueWithCurrencyEffect = transactionInvestmentWithCurrencyEffect
            fees = fees.plus((order.fee_in_base_currency if order.fee_in_base_currency is not None else 0))
            feesWithCurrencyEffect = feesWithCurrencyEffect.plus((order.fee_in_base_currency_with_currency_effect if order.fee_in_base_currency_with_currency_effect is not None else 0))
            totalUnits = totalUnits.plus(order.quantity.mul(getFactor(order.type)))
            valueOfInvestment = totalUnits.mul(marketPriceInBaseCurrency)
            valueOfInvestmentWithCurrencyEffect = totalUnits.mul(marketPriceInBaseCurrencyWithCurrencyEffect)
            grossPerformanceFromSell = (order.unit_price_in_base_currency.minus(lastAveragePrice).mul(order.quantity) if (order.type == 'SELL') else Big(0))
            grossPerformanceFromSellWithCurrencyEffect = (order.unit_price_in_base_currency_with_currency_effect.minus(lastAveragePriceWithCurrencyEffect).mul(order.quantity) if (order.type == 'SELL') else Big(0))
            grossPerformanceFromSells = grossPerformanceFromSells.plus(grossPerformanceFromSell)
            grossPerformanceFromSellsWithCurrencyEffect = grossPerformanceFromSellsWithCurrencyEffect.plus(grossPerformanceFromSellWithCurrencyEffect)
            lastAveragePrice = (Big(0) if totalQuantityFromBuyTransactions.eq(0) else totalInvestmentFromBuyTransactions.div(totalQuantityFromBuyTransactions))
            lastAveragePriceWithCurrencyEffect = (Big(0) if totalQuantityFromBuyTransactions.eq(0) else totalInvestmentFromBuyTransactionsWithCurrencyEffect.div(totalQuantityFromBuyTransactions))
            if (totalUnits.eq(0)):
                # Reset tracking variables when position is fully closed
                totalInvestmentFromBuyTransactions = Big(0)
                totalInvestmentFromBuyTransactionsWithCurrencyEffect = Big(0)
                totalQuantityFromBuyTransactions = Big(0)
            if (PortfolioCalculator.ENABLE_LOGGING):
                console.log('grossPerformanceFromSells', grossPerformanceFromSells.to_number())
                console.log('grossPerformanceFromSellWithCurrencyEffect', grossPerformanceFromSellWithCurrencyEffect.to_number())
            newGrossPerformance = valueOfInvestment.minus(totalInvestment).plus(grossPerformanceFromSells)
            newGrossPerformanceWithCurrencyEffect = valueOfInvestmentWithCurrencyEffect.minus(totalInvestmentWithCurrencyEffect).plus(grossPerformanceFromSellsWithCurrencyEffect)
            grossPerformance = newGrossPerformance
            grossPerformanceWithCurrencyEffect = newGrossPerformanceWithCurrencyEffect
            if ((order.item_type == 'start')):
                feesAtStartDate = fees
                feesAtStartDateWithCurrencyEffect = feesWithCurrencyEffect
                grossPerformanceAtStartDate = grossPerformance
                grossPerformanceAtStartDateWithCurrencyEffect = grossPerformanceWithCurrencyEffect
            if ((i > indexOfStartOrder)):
                # Only consider periods with an investment for the calculation of
                # the time weighted investment
                if ((valueOfInvestmentBeforeTransaction.gt(0) and (order.type in ['BUY', 'SELL']))):
                    # Calculate the number of days since the previous order
                    orderDate = Date(order.date)
                    previousOrderDate = Date(orders[(i - 1)].date)
                    daysSinceLastOrder = differenceInDays(orderDate, previousOrderDate)
                    if ((daysSinceLastOrder <= 0)):
                        # The time between two activities on the same day is unknown
                        # -> Set it to the smallest floating point number greater than 0
                        daysSinceLastOrder = Number.EPSILON
                    # Sum up the total investment days since the start date to calculate
                    # the time weighted investment
                    totalInvestmentDays += daysSinceLastOrder
                    sumOfTimeWeightedInvestments = sumOfTimeWeightedInvestments.add(valueAtStartDate.minus(investmentAtStartDate).plus(totalInvestmentBeforeTransaction).mul(daysSinceLastOrder))
                    sumOfTimeWeightedInvestmentsWithCurrencyEffect = sumOfTimeWeightedInvestmentsWithCurrencyEffect.add(valueAtStartDateWithCurrencyEffect.minus(investmentAtStartDateWithCurrencyEffect).plus(totalInvestmentBeforeTransactionWithCurrencyEffect).mul(daysSinceLastOrder))
                currentValues[order.date] = valueOfInvestment
                currentValuesWithCurrencyEffect[order.date] = valueOfInvestmentWithCurrencyEffect
                netPerformanceValues[order.date] = grossPerformance.minus(grossPerformanceAtStartDate).minus(fees.minus(feesAtStartDate))
                netPerformanceValuesWithCurrencyEffect[order.date] = grossPerformanceWithCurrencyEffect.minus(grossPerformanceAtStartDateWithCurrencyEffect).minus(feesWithCurrencyEffect.minus(feesAtStartDateWithCurrencyEffect))
                investmentValuesAccumulated[order.date] = totalInvestment
                investmentValuesAccumulatedWithCurrencyEffect[order.date] = totalInvestmentWithCurrencyEffect
                investmentValuesWithCurrencyEffect[order.date] = ((investmentValuesWithCurrencyEffect[order.date] if investmentValuesWithCurrencyEffect[order.date] is not None else Big(0))).add(transactionInvestmentWithCurrencyEffect)
                # If duration is effectively zero (first day), use the actual investment as the base.
                # Otherwise, use the calculated time-weighted average.
                timeWeightedInvestmentValues[order.date] = (sumOfTimeWeightedInvestments.div(totalInvestmentDays) if (totalInvestmentDays > Number.EPSILON) else (totalInvestment if totalInvestment.gt(0) else Big(0)))
                timeWeightedInvestmentValuesWithCurrencyEffect[order.date] = (sumOfTimeWeightedInvestmentsWithCurrencyEffect.div(totalInvestmentDays) if (totalInvestmentDays > Number.EPSILON) else (totalInvestmentWithCurrencyEffect if totalInvestmentWithCurrencyEffect.gt(0) else Big(0)))
            if (PortfolioCalculator.ENABLE_LOGGING):
                console.log('totalInvestment', totalInvestment.to_number())
                console.log('totalInvestmentWithCurrencyEffect', totalInvestmentWithCurrencyEffect.to_number())
                console.log('totalGrossPerformance', grossPerformance.minus(grossPerformanceAtStartDate).to_number())
                console.log('totalGrossPerformanceWithCurrencyEffect', grossPerformanceWithCurrencyEffect.minus(grossPerformanceAtStartDateWithCurrencyEffect).to_number())
            if ((i == indexOfEndOrder)):
                break
            i += 1
        totalGrossPerformance = grossPerformance.minus(grossPerformanceAtStartDate)
        totalGrossPerformanceWithCurrencyEffect = grossPerformanceWithCurrencyEffect.minus(grossPerformanceAtStartDateWithCurrencyEffect)
        totalNetPerformance = grossPerformance.minus(grossPerformanceAtStartDate).minus(fees.minus(feesAtStartDate))
        timeWeightedAverageInvestmentBetweenStartAndEndDate = (sumOfTimeWeightedInvestments.div(totalInvestmentDays) if (totalInvestmentDays > 0) else Big(0))
        timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect = (sumOfTimeWeightedInvestmentsWithCurrencyEffect.div(totalInvestmentDays) if (totalInvestmentDays > 0) else Big(0))
        grossPerformancePercentage = (totalGrossPerformance.div(timeWeightedAverageInvestmentBetweenStartAndEndDate) if timeWeightedAverageInvestmentBetweenStartAndEndDate.gt(0) else Big(0))
        grossPerformancePercentageWithCurrencyEffect = (totalGrossPerformanceWithCurrencyEffect.div(timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect) if timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect.gt(0) else Big(0))
        feesPerUnit = (fees.minus(feesAtStartDate).div(totalUnits) if totalUnits.gt(0) else Big(0))
        feesPerUnitWithCurrencyEffect = (feesWithCurrencyEffect.minus(feesAtStartDateWithCurrencyEffect).div(totalUnits) if totalUnits.gt(0) else Big(0))
        netPerformancePercentage = (totalNetPerformance.div(timeWeightedAverageInvestmentBetweenStartAndEndDate) if timeWeightedAverageInvestmentBetweenStartAndEndDate.gt(0) else Big(0))
        netPerformancePercentageWithCurrencyEffectMap = {}
        netPerformanceWithCurrencyEffectMap = {}
        for dateRange in ['1d', '1y', '5y', 'max', 'mtd', 'wtd', 'ytd', *eachYearOfInterval({'end': end, 'start': start}).filter((lambda date: (not isThisYear(date)))).map((lambda date: format(date, 'yyyy')))]:
            dateInterval = getIntervalFromDateRange(dateRange)
            endDate = dateInterval.end_date
            startDate = dateInterval.start_date
            if (isBefore(startDate, start)):
                startDate = start
            rangeEndDateString = format(endDate, DATE_FORMAT)
            rangeStartDateString = format(startDate, DATE_FORMAT)
            currentValuesAtDateRangeStartWithCurrencyEffect = (currentValuesWithCurrencyEffect[rangeStartDateString] if currentValuesWithCurrencyEffect[rangeStartDateString] is not None else Big(0))
            investmentValuesAccumulatedAtStartDateWithCurrencyEffect = (investmentValuesAccumulatedWithCurrencyEffect[rangeStartDateString] if investmentValuesAccumulatedWithCurrencyEffect[rangeStartDateString] is not None else Big(0))
            grossPerformanceAtDateRangeStartWithCurrencyEffect = currentValuesAtDateRangeStartWithCurrencyEffect.minus(investmentValuesAccumulatedAtStartDateWithCurrencyEffect)
            average = Big(0)
            dayCount = 0
            i = (self.chart_dates.length - 1)
            while (i >= 0):
                date = self.chart_dates[i]
                if ((date > rangeEndDateString)):
                    continue
                elif ((date < rangeStartDateString)):
                    break
                if ((isinstance(investmentValuesAccumulatedWithCurrencyEffect[date], Big) and investmentValuesAccumulatedWithCurrencyEffect[date].gt(0))):
                    average = average.add(investmentValuesAccumulatedWithCurrencyEffect[date].add(grossPerformanceAtDateRangeStartWithCurrencyEffect))
                    dayCount += 1
                i -= 1
            if ((dayCount > 0)):
                average = average.div(dayCount)
            netPerformanceWithCurrencyEffectMap[dateRange] = (netPerformanceValuesWithCurrencyEffect[rangeEndDateString].minus(__unhandled_comment__, __unhandled_comment__, __unhandled_comment__, (Big(0) if (dateRange == 'max') else ((netPerformanceValuesWithCurrencyEffect[rangeStartDateString] if netPerformanceValuesWithCurrencyEffect[rangeStartDateString] is not None else Big(0))))) if netPerformanceValuesWithCurrencyEffect[rangeEndDateString].minus(__unhandled_comment__, __unhandled_comment__, __unhandled_comment__, (Big(0) if (dateRange == 'max') else ((netPerformanceValuesWithCurrencyEffect[rangeStartDateString] if netPerformanceValuesWithCurrencyEffect[rangeStartDateString] is not None else Big(0))))) is not None else Big(0))
            netPerformancePercentageWithCurrencyEffectMap[dateRange] = (netPerformanceWithCurrencyEffectMap[dateRange].div(average) if average.gt(0) else Big(0))
        if (PortfolioCalculator.ENABLE_LOGGING):
            console.log(f"\n        {symbol}\n        Unit price: {orders[indexOfStartOrder].unit_price.to_fixed(2)} -> {unitPriceAtEndDate.to_fixed(2)}\n        Total investment: {totalInvestment.to_fixed(2)}\n        Total investment with currency effect: {totalInvestmentWithCurrencyEffect.to_fixed(2)}\n        Time weighted investment: {timeWeightedAverageInvestmentBetweenStartAndEndDate.to_fixed(2)}\n        Time weighted investment with currency effect: {timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect.to_fixed(2)}\n        Total dividend: {totalDividend.to_fixed(2)}\n        Gross performance: {totalGrossPerformance.to_fixed(2)} / {grossPerformancePercentage.mul(100).to_fixed(2)}%\n        Gross performance with currency effect: {totalGrossPerformanceWithCurrencyEffect.to_fixed(2)} / {grossPerformancePercentageWithCurrencyEffect.mul(100).to_fixed(2)}%\n        Fees per unit: {feesPerUnit.to_fixed(2)}\n        Fees per unit with currency effect: {feesPerUnitWithCurrencyEffect.to_fixed(2)}\n        Net performance: {totalNetPerformance.to_fixed(2)} / {netPerformancePercentage.mul(100).to_fixed(2)}%\n        Net performance with currency effect: {netPerformancePercentageWithCurrencyEffectMap['max'].to_fixed(2)}%")
        return {'currentValues': currentValues, 'currentValuesWithCurrencyEffect': currentValuesWithCurrencyEffect, 'feesWithCurrencyEffect': feesWithCurrencyEffect, 'grossPerformancePercentage': grossPerformancePercentage, 'grossPerformancePercentageWithCurrencyEffect': grossPerformancePercentageWithCurrencyEffect, 'initialValue': initialValue, 'initialValueWithCurrencyEffect': initialValueWithCurrencyEffect, 'investmentValuesAccumulated': investmentValuesAccumulated, 'investmentValuesAccumulatedWithCurrencyEffect': investmentValuesAccumulatedWithCurrencyEffect, 'investmentValuesWithCurrencyEffect': investmentValuesWithCurrencyEffect, 'netPerformancePercentage': netPerformancePercentage, 'netPerformancePercentageWithCurrencyEffectMap': netPerformancePercentageWithCurrencyEffectMap, 'netPerformanceValues': netPerformanceValues, 'netPerformanceValuesWithCurrencyEffect': netPerformanceValuesWithCurrencyEffect, 'netPerformanceWithCurrencyEffectMap': netPerformanceWithCurrencyEffectMap, 'timeWeightedInvestmentValues': timeWeightedInvestmentValues, 'timeWeightedInvestmentValuesWithCurrencyEffect': timeWeightedInvestmentValuesWithCurrencyEffect, 'totalAccountBalanceInBaseCurrency': totalAccountBalanceInBaseCurrency, 'totalDividend': totalDividend, 'totalDividendInBaseCurrency': totalDividendInBaseCurrency, 'totalInterest': totalInterest, 'totalInterestInBaseCurrency': totalInterestInBaseCurrency, 'totalInvestment': totalInvestment, 'totalInvestmentWithCurrencyEffect': totalInvestmentWithCurrencyEffect, 'totalLiabilities': totalLiabilities, 'totalLiabilitiesInBaseCurrency': totalLiabilitiesInBaseCurrency, 'grossPerformance': totalGrossPerformance, 'grossPerformanceWithCurrencyEffect': totalGrossPerformanceWithCurrencyEffect, 'hasErrors': (totalUnits.gt(0) and (((not initialValue) or (not unitPriceAtEndDate)))), 'netPerformance': totalNetPerformance, 'timeWeightedInvestment': timeWeightedAverageInvestmentBetweenStartAndEndDate, 'timeWeightedInvestmentWithCurrencyEffect': timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect}

