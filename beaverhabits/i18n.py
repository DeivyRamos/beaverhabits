"""Spanish labels for dates, independent of the server's OS locale."""

import datetime

DAY_ABBR = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]  # Monday first
DAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTH_ABBR = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MONTH_NAMES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def day_abbr(day: datetime.date) -> str:
    return DAY_ABBR[day.weekday()]


def month_abbr(month: int) -> str:
    return MONTH_ABBR[month]


def long_date(day: datetime.date) -> str:
    """e.g. '12 de noviembre de 2026'."""
    return f"{day.day} de {MONTH_NAMES[day.month]} de {day.year}"


# Locale object for Quasar's QDate component (Sunday first, as Quasar expects).
QUASAR_DATE_LOCALE = {
    "days": [d.capitalize() for d in DAY_NAMES[6:] + DAY_NAMES[:6]],
    "daysShort": DAY_ABBR[6:] + DAY_ABBR[:6],
    "months": [m.capitalize() for m in MONTH_NAMES[1:]],
    "monthsShort": MONTH_ABBR[1:],
}
