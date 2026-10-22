"""Gregorian to Ethiopian calendar conversion for invoices.

Follows the arithmetic in Reingold & Dershowitz, Calendrical Calculations. The Ethiopian year has 12 months of 30 days
plus Pagume (5 days, or 6 in the year before a Gregorian leap year).
"""

import datetime

MONTHS_EN = [
    "Meskerem", "Tikimt", "Hidar", "Tahsas", "Tir", "Yekatit",
    "Megabit", "Miyazya", "Ginbot", "Sene", "Hamle", "Nehase", "Pagume",
]
MONTHS_AM = [
    "መስከረም", "ጥቅምት", "ኅዳር", "ታኅሣሥ", "ጥር", "የካቲት",
    "መጋቢት", "ሚያዝያ", "ግንቦት", "ሰኔ", "ሐምሌ", "ነሐሴ", "ጳጉሜ",
]
_ETHIOPIC_EPOCH = 2796  # R.D. (proleptic Gregorian ordinal) of 1 Meskerem 1 E.C.


def _fixed_from_ethiopian(year, month, day):
    return _ETHIOPIC_EPOCH - 1 + 365 * (year - 1) + year // 4 + 30 * (month - 1) + day


def to_ethiopian(day: datetime.date):
    fixed = day.toordinal()
    year = (4 * (fixed - _ETHIOPIC_EPOCH) + 1463) // 1461
    month = (fixed - _fixed_from_ethiopian(year, 1, 1)) // 30 + 1
    date = fixed + 1 - _fixed_from_ethiopian(year, month, 1)
    return year, month, date


def format_ethiopian(day: datetime.date, lang="en"):
    year, month, date = to_ethiopian(day)
    names = MONTHS_AM if lang == "am" else MONTHS_EN
    return f"{names[month - 1]} {date}, {year} E.C." if lang != "am" else f"{names[month - 1]} {date} ቀን {year} ዓ.ም."
