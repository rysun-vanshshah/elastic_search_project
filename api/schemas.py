# ==============================================================================
# API SCHEMAS & MODELS (api/schemas.py)
# Pydantic models for request/response validation and Swagger UI documentation.
# ==============================================================================

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class FiltersApplied(BaseModel):
    """Reflects the exact filters applied to the search query."""
    search_term: Optional[str] = Field(None, description="Cleaned keyword search term")
    min_price: Optional[float] = Field(None, description="Active minimum price filter")
    max_price: Optional[float] = Field(None, description="Active maximum price filter")
    category: Optional[str] = Field(None, description="Active category filter")
    brand: Optional[str] = Field(None, description="Active brand filter")
    sort_by: str = Field("relevance", description="Active sorting order")


class SearchResponse(BaseModel):
    """Standardized response schema returned by the /search endpoint."""
    total_records: int = Field(..., description="Total matching product count")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of results per page")
    filters_applied: FiltersApplied = Field(..., description="Summary of all active search filters")
    available_categories: List[str] = Field(default_factory=list, description="Categories matching query")
    available_brands: List[str] = Field(default_factory=list, description="Brands matching query")
    elasticsearch_query: Dict[str, Any] = Field(default_factory=dict, description="Generated Elasticsearch query")
    products: List[Dict[str, Any]] = Field(default_factory=list, description="List of matching product documents")
