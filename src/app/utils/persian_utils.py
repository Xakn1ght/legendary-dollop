def persian_to_ascii(text: str) -> str:
    """
    Convert Persian/Farsi digits to ASCII digits.
    
    Persian digits: ۰ ۱ ۲ ۳ ۴ ۵ ۶ ۷ ۸ ۹
    ASCII digits:   0 1 2 3 4 5 6 7 8 9
    """
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    ascii_digits = '0123456789'
    
    # Create translation table
    translation_table = str.maketrans(persian_digits, ascii_digits)
    
    # Apply translation
    return text.translate(translation_table)


def normalize_number_input(text: str) -> str:
    """
    Normalize number input by converting Persian digits to ASCII
    and handling both comma and dot as decimal separators.
    """
    if not text:
        return text
    
    # Convert Persian digits to ASCII
    normalized = persian_to_ascii(text)
    
    # Replace Persian comma with dot for decimal separator
    normalized = normalized.replace(',', '.')
    
    return normalized


def parse_float_persian(text: str) -> float:
    """
    Parse a float from text that may contain Persian digits.
    Raises ValueError if the text is not a valid number.
    """
    normalized = normalize_number_input(text)
    return float(normalized)


def parse_int_persian(text: str) -> int:
    """
    Parse an integer from text that may contain Persian digits.
    Raises ValueError if the text is not a valid integer.
    """
    normalized = normalize_number_input(text)
    
    # Check if it's a whole number (no decimal point)
    if '.' in normalized:
        # If it has decimal point, check if it's effectively an integer
        float_val = float(normalized)
        if float_val.is_integer():
            return int(float_val)
        else:
            raise ValueError("Not a valid integer")
    
    return int(normalized) 