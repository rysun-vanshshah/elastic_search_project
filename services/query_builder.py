# ==============================================================================
# ELASTICSEARCH QUERY BUILDER (services/query_builder.py)
# Assembles Elasticsearch Query DSL, aggregations, sorting, and dropdown filters.
# Reusable across API endpoints, background jobs, and tests.
# ==============================================================================

from typing import Optional, List, Dict, Any, Tuple

# Field priorities: Higher boost (^) = higher importance in search ranking
SEARCH_FIELDS: List[str] = [
    "product_name^10",  # 10x priority: title match
    "category^5",      # 5x priority: category match
    "brand^3",         # 3x priority: brand match
    "description^2",   # 2x priority: description match
]

# Supported sort options mapped to Elasticsearch sort rules
SORT_OPTIONS: Dict[str, List[Dict[str, Any]]] = {
    "relevance": [{"_score": {"order": "desc"}}],
    "price_asc": [{"price": {"order": "asc"}}],
    "price_desc": [{"price": {"order": "desc"}}],
    "rating_desc": [{"rating": {"order": "desc"}}],
    "name_asc": [{"product_name.keyword": {"order": "asc"}}],
}


def build_search_query(
    search_term: Optional[str],
    category: Optional[str],
    brand: Optional[str],
    min_price: Optional[float],
    max_price: Optional[float],
    sort_by: Optional[str]
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any], str]:
    """
    Constructs the Elasticsearch search query, filters, aggregations, and sort rules.

    Returns:
        (query_body, category_filter, sort_rules, aggregations, clean_sort)
    """
    # 1. Text Search (matches keywords or returns all products if query is empty)
    if search_term and search_term.strip():
        must_clause = [{
            "multi_match": {
                "query": search_term.strip(),
                "fields": SEARCH_FIELDS,
                "type": "best_fields",
                "operator": "and",
                "fuzziness": "AUTO"
            }
        }]
    else:
        must_clause = [{"match_all": {}}]

    # 2. Strict Filters (active status, brand, and price bounds)
    filters: List[Dict[str, Any]] = [{"term": {"is_active": True}}]

    if brand:
        filters.append({"term": {"brand": {"value": brand, "case_insensitive": True}}})

    if min_price is not None or max_price is not None:
        price_filter: Dict[str, float] = {}
        if min_price is not None:
            price_filter["gte"] = min_price
        if max_price is not None:
            price_filter["lte"] = max_price
        filters.append({"range": {"price": price_filter}})

    # Assemble main query body
    query_body = {
        "bool": {
            "must": must_clause,
            "filter": filters
        }
    }

    # 3. Category Post-Filter (keeps all categories visible in sidebar dropdown)
    category_filter = {"match": {"category": category}} if category else None

    # 4. Aggregations (fetches list of available categories and scoped brands)
    aggregations = {
        "available_categories": {
            "terms": {
                "field": "category.keyword",
                "size": 50,
                "order": {"_key": "asc"}
            }
        },
        "scoped_brands": {
            "filter": {"match": {"category": category}} if category else {"match_all": {}},
            "aggs": {
                "available_brands": {
                    "terms": {
                        "field": "brand",
                        "size": 100,
                        "order": {"_key": "asc"}
                    }
                }
            }
        }
    }

    # 5. Sorting
    clean_sort = (sort_by or "relevance").lower().strip()
    sort_rules = SORT_OPTIONS.get(clean_sort, SORT_OPTIONS["relevance"])

    return query_body, category_filter, sort_rules, aggregations, clean_sort


def extract_filter_options(aggregations_data: Dict[str, Any], *nested_keys: str) -> List[str]:
    """Safely extracts category or brand names from Elasticsearch aggregation buckets."""
    current = aggregations_data
    for key in nested_keys:
        if not isinstance(current, dict):
            return []
        current = current.get(key, {})

    buckets = current.get("buckets", []) if isinstance(current, dict) else []
    return [item["key"] for item in buckets if isinstance(item, dict) and "key" in item]


def sync_brand_and_category(
    selected_brand: Optional[str],
    selected_category: Optional[str],
    available_brands: List[str],
    available_categories: List[str]
) -> Tuple[Optional[str], Optional[str]]:
    """
    Keeps brand and category dropdowns synchronized:
    - Normalizes letter casing (e.g. 'dell' -> 'Dell').
    - Auto-selects category if the brand belongs to only one category.
    - Clears brand if it does not exist in the selected category.
    """
    # 1. Normalize brand casing
    if selected_brand:
        for b in available_brands:
            if b.lower() == selected_brand.lower():
                selected_brand = b
                break

    # 2. Normalize category casing
    if selected_category:
        for c in available_categories:
            if c.lower() == selected_category.lower():
                selected_category = c
                break

    # 3. Auto-select category if brand only has one category
    if selected_brand and (not selected_category or selected_category not in available_categories):
        if len(available_categories) == 1:
            selected_category = available_categories[0]

    # 4. Clear brand if it doesn't belong to the selected category
    if selected_category and selected_brand and selected_brand not in available_brands:
        selected_brand = None

    return selected_brand, selected_category
