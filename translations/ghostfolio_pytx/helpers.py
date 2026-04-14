def each_day_of_interval(start, end):
    current = start
    while current <= end:
        yield current
        current = current + timedelta(days=1)

def _add_years(d, years):
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)

def each_year_of_interval(start, end):
    current = start
    while current <= end:
        yield current
        current = _add_years(current, 1)
