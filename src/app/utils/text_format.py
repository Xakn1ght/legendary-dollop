from datetime import datetime

import jdatetime


def to_persian_digits(text: str | int) -> str:
    """Converts English digits in a string to Persian digits."""
    text = str(text)
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    translation_table = str.maketrans(english_digits, persian_digits)
    return text.translate(translation_table)

def to_jalali_date(gregorian_date: datetime) -> str:
    """Converts a Gregorian datetime object to a formatted Jalali date string with Persian digits."""
    if not gregorian_date:
        return ""
    try:
        jalali = jdatetime.datetime.fromgregorian(datetime=gregorian_date)
        formatted_date = jalali.strftime('%Y/%m/%d')
        return to_persian_digits(formatted_date)
    except (ValueError, TypeError):
        # Fallback for invalid dates
        return str(gregorian_date)
