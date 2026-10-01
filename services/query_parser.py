# ==============================================================================
# NATURAL LANGUAGE QUERY & PRICE PARSER (services/query_parser.py)
# Extracts price constraints and clean product keywords from user search text.
# Supports comma formats (1,20,000), Indian units (Lakh, Crore), and 'k'.
# ==============================================================================

import re
from typing import Optional, Tuple


def _convert_to_price_number(price_str: str) -> float:
    """
    Converts text price values into a plain float number.
    Supports:
    - Comma formats: '1,20,000', '120,000', '15,000'
    - Indian units: '1.2 lakh', '1.5L', '2 crore', '50k'
    - Currency prefixes: '₹1,20,000', 'rs 15k', '$499'
    """
    cleaned = price_str.lower().strip()
    # Remove currency symbols (₹, $, €, £, rs, inr)
    cleaned = re.sub(r'^(?:rs\.?|inr|₹|\$|€|£)\s*', '', cleaned)
    cleaned = re.sub(r'\s*(?:rs\.?|inr|₹|\$|€|£)$', '', cleaned)
    # Remove commas
    cleaned = cleaned.replace(',', '').strip()

    # Match Indian Lakh/Lac/L (e.g., '1.2 lakh', '1.5l')
    if re.search(r'\s*(?:lakhs?|lac|l)$', cleaned):
        num_part = re.sub(r'\s*(?:lakhs?|lac|l)$', '', cleaned).strip()
        return float(num_part) * 100000.0

    # Match Indian Crore/Cr (e.g., '2 crore', '1cr')
    if re.search(r'\s*(?:crores?|cr)$', cleaned):
        num_part = re.sub(r'\s*(?:crores?|cr)$', '', cleaned).strip()
        return float(num_part) * 10000000.0

    # Match Thousands 'k' (e.g., '15k')
    if cleaned.endswith('k'):
        return float(cleaned[:-1].strip()) * 1000.0

    return float(cleaned)


def extract_price_from_query(search_text: Optional[str]) -> Tuple[Optional[str], Optional[float], Optional[float]]:
    """
    Detects and extracts price words from user search text:
    - 'mobile phones under 1,20,000' -> text='mobile phones', max_price=120000.0
    - 'phones under 15k'             -> text='phones', max_price=15000.0
    - 'laptops under 1.5 lakh'       -> text='laptops', max_price=150000.0
    - 'shoes between 2,000 and 5,000' -> text='shoes', min_price=2000.0, max_price=5000.0
    - 'laptops above 40,000'         -> text='laptops', min_price=40000.0
    """
    min_price = None
    max_price = None

    if not search_text:
        return None, min_price, max_price

    clean_text = search_text

    # Price pattern matches commas in numbers (1,20,000 or 120,000), decimals, units (k, lakh, crore), and currency symbols
    price_pattern = r'(?:(?:rs\.?|inr|₹|\$|€|£)\s*)?[\d,]+(?:\.\d+)?(?:\s*(?:k|lakhs?|lac|l|crores?|cr)\b)?(?:\s*(?:rs\.?|inr|₹|\$|€|£))?'

    # 1. Match price ranges: 'between X and Y', 'X to Y', 'X - Y'
    range_regex = rf'\b(?:between\s+)?({price_pattern})\s*(?:to|-|and)\s*({price_pattern})(?=\s|$|[.,;!?])'
    range_match = re.search(range_regex, clean_text, re.IGNORECASE)
    if range_match:
        try:
            min_price = _convert_to_price_number(range_match.group(1))
            max_price = _convert_to_price_number(range_match.group(2))
            clean_text = re.sub(range_regex, '', clean_text, flags=re.IGNORECASE).strip()
        except ValueError:
            pass

    # 2. Match upper limits: 'under / below / less than / cheaper than / <= / < X'
    under_regex = rf'\b(?:under|below|less than|cheaper than|<=|<)\s*({price_pattern})(?=\s|$|[.,;!?])'
    under_match = re.search(under_regex, clean_text, re.IGNORECASE)
    if under_match:
        try:
            max_price = _convert_to_price_number(under_match.group(1))
            clean_text = re.sub(under_regex, '', clean_text, flags=re.IGNORECASE).strip()
        except ValueError:
            pass

    # 3. Match lower limits: 'above / over / more than / greater than / >= / > X'
    above_regex = rf'\b(?:above|over|more than|greater than|>=|>)\s*({price_pattern})(?=\s|$|[.,;!?])'
    above_match = re.search(above_regex, clean_text, re.IGNORECASE)
    if above_match:
        try:
            min_price = _convert_to_price_number(above_match.group(1))
            clean_text = re.sub(above_regex, '', clean_text, flags=re.IGNORECASE).strip()
        except ValueError:
            pass

    # Clean leftover punctuation or extra spaces
    clean_text = re.sub(r'[,;!?]', ' ', clean_text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    return clean_text if clean_text else None, min_price, max_price
