# ==============================================================================
# PRODUCT SYNONYMS CONFIGURATION (config/synonyms.py)
# Centralized synonym list used by the Elasticsearch custom analyzer.
# Easy to maintain and expand by any developer or business user.
# ==============================================================================

from typing import List

PRODUCT_SYNONYMS: List[str] = [
    "mobile, mobile phone, smartphone, smart phone, cell phone, cellphone, phone",
    "laptop, notebook, pc, computer",
    "shoe, shoes, footwear, sneaker, sneakers",
    "watch, watches, smartwatch, smart watch",
    "headphone, headphones, earphone, earphones, earbuds, airpods",
    "tv, tvs, smart tv, television",
]
