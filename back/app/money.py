"""Money is stored as whole paise so adding it up is always exact. The API speaks in rupees."""


def to_paise(rupees) -> int:
    return int(round(float(rupees or 0) * 100))


def rupees(paise) -> float:
    return round((paise or 0) / 100, 2)
