def _d(v):
    if isinstance(v, Decimal): return v
    if v is None: return Decimal('0')
    return Decimal(str(v))
