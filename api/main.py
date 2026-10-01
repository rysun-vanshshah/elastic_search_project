# ==============================================================================
# FASTAPI PRODUCT SEARCH API (api/main.py)
# Lightweight HTTP Controller for the Product Search Engine.
# ==============================================================================

from typing import Optional, Dict, Any
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config.logger import get_logger
from services.elastic_service import ElasticService
from services.query_parser import extract_price_from_query
from services.query_builder import (
    build_search_query,
    sync_brand_and_category,
    extract_filter_options,
)
from api.schemas import SearchResponse

logger = get_logger("ProductSearchAPI")

# ==============================================================================
# FASTAPI APP & ELASTICSEARCH SERVICE SETUP
# ==============================================================================
app = FastAPI(
    title="Product Searchbar API",
    description="Search Engine with Typo Tolerance, Synonyms, and Dynamic Filters",
    version="1.0.0"
)

# Enable CORS for browser frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Elasticsearch service
elastic_service = ElasticService()
elastic_service.connect()


# ==============================================================================
# ROUTE 1: WELCOME / ROOT ENDPOINT
# ==============================================================================
@app.get("/")
def home():
    """Simple welcome route redirecting users to Swagger UI documentation."""
    return {"message": "Product Search API is running! Open /docs to test endpoints."}


# ==============================================================================
# ROUTE 2: PRODUCT SEARCH ENDPOINT
# ==============================================================================
@app.get("/search", response_model=SearchResponse)
def search_products(
    q: Optional[str] = Query(None, description="Search keyword (e.g. 'shoes under 2000', 'phones 15k')"),
    category: Optional[str] = Query(None, description="Filter by category name (e.g. Electronics, Computers, Footwear)"),
    brand: Optional[str] = Query(None, description="Filter by brand name (e.g. Nike, Adidas, Dell)"),
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    sort_by: Optional[str] = Query("relevance", description="Sort option: relevance, price_asc, price_desc, rating_desc, name_asc"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    size: int = Query(10, ge=1, le=50, description="Number of results per page")
):
    """
    Product Search Endpoint:
    - Parses natural language price constraints ('mobile phones under 1,20,000')
    - Matches synonyms and typos automatically via Elasticsearch
    - Dynamic brand and category filters and pagination
    """
    try:
        start_offset = (page - 1) * size

        # 1. Extract search term and price limits from query text
        clean_text, extracted_min_price, extracted_max_price = extract_price_from_query(q)
        final_min_price = min_price if min_price is not None else extracted_min_price
        final_max_price = max_price if max_price is not None else extracted_max_price

        # Clean string inputs
        clean_category = category.strip() if category and category.strip() else None
        clean_brand = brand.strip() if brand and brand.strip() else None

        # 2. Build search query, filters, sort rules, and aggregations
        query_body, category_filter, sort_rules, aggregations, clean_sort = build_search_query(
            search_term=clean_text,
            category=clean_category,
            brand=clean_brand,
            min_price=final_min_price,
            max_price=final_max_price,
            sort_by=sort_by
        )

        # 3. Assemble parameters and execute search
        search_params: Dict[str, Any] = {
            "query": query_body,
            "sort": sort_rules,
            "aggregations": aggregations,
            "from_": start_offset,
            "size": size,
            "track_total_hits": True
        }
        if category_filter:
            search_params["post_filter"] = category_filter

        response = elastic_service.search(**search_params)

        # 4. Extract products and filter options safely
        total_records = response["hits"]["total"]["value"]
        products = [hit["_source"] for hit in response["hits"]["hits"]]

        raw_aggs = response.get("aggregations", {})
        available_categories = extract_filter_options(raw_aggs, "available_categories")
        available_brands = extract_filter_options(raw_aggs, "scoped_brands", "available_brands")

        # 5. Synchronize brand and category selections
        clean_brand, clean_category = sync_brand_and_category(
            selected_brand=clean_brand,
            selected_category=clean_category,
            available_brands=available_brands,
            available_categories=available_categories
        )

        # Assemble generated core query (search conditions & filters)
        generated_query: Dict[str, Any] = {"query": query_body}
        if category_filter:
            generated_query["post_filter"] = category_filter

        # 6. Return response
        return {
            "total_records": total_records,
            "page": page,
            "size": size,
            "filters_applied": {
                "search_term": clean_text,
                "min_price": final_min_price,
                "max_price": final_max_price,
                "category": clean_category,
                "brand": clean_brand,
                "sort_by": clean_sort
            },
            "available_categories": available_categories,
            "available_brands": available_brands,
            "elasticsearch_query": generated_query,
            "products": products
        }

    except Exception as e:
        logger.error(f"Search endpoint request failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# ==============================================================================
# SERVER ENTRY POINT (Uvicorn Launcher)
# ==============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
