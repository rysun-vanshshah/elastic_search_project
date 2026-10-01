# 🛍️ Elasticsearch Product Search Engine & ETL Pipeline

A production-grade e-commerce search solution featuring:
1. **Automated ETL Pipeline**: Ingests product catalog data from **Microsoft SQL Server** (`vansh.dbo.products`) into **Elasticsearch** with **Incremental Sync** and automatic checkpoint tracking.
2. **FastAPI Search Engine**: High-performance REST API powered by **Elasticsearch Query DSL**, supporting natural language price parsing, bidirectional synonyms, typo tolerance, dynamic faceted aggregations, and strict relevance.
3. **Interactive Frontend Hub**: Modern UI featuring Product Cards, Raw Response JSON, and a live **Elasticsearch Query Inspector**.

---

## 📁 Project Architecture

```text
ES_Project/
├── api/
│   ├── main.py              # FastAPI app & routing controller (GET /search)
│   └── schemas.py           # Pydantic models for request/response validation & Swagger UI
├── config/
│   ├── settings.py          # Environment settings loader (.env) & SQL connection string
│   ├── logger.py            # Centralized logger configuration (timestamps & warning suppression)
│   └── synonyms.py          # Centralized, easily editable product synonym dictionary
├── services/
│   ├── query_parser.py      # Natural language & price intent parser (commas, Lakh, Crore, k)
│   ├── query_builder.py     # Elasticsearch Query DSL generator, filters & facet harmonization
│   ├── elastic_service.py   # Elasticsearch connection, custom analyzers & bulk indexing
│   ├── sql_service.py       # SQL Server batch reader with Python context manager (with sql:)
│   └── checkpoint_service.py# Checkpoint tracker with crash-safe atomic file writing
├── tests/
│   └── test_search.py       # Automated unit tests for query parser & query builder
├── frontend/
│   └── index.html           # Interactive 3-tab search frontend
├── sync_pipeline.py         # ETL sync runner script (Full & Incremental)
├── sync_state.json          # Checkpoint tracking file
├── .env                     # Credentials & configuration (git-ignored)
├── .env.example             # Template for environment variables
├── requirements.txt         # Project dependencies
└── README.md                # Documentation
```

---

## ✨ Key Features & Capabilities

### 1. Natural Language Price Intent Extraction
Users can search naturally, and the engine automatically extracts price boundaries while keeping the core product keyword:
- `"mobile phones under 1,20,000"` $\rightarrow$ Searches `mobile phones` with `price <= 120000.0`
- `"shoes between 2000 and 5000"` $\rightarrow$ Searches `shoes` with `price >= 2000.0` and `price <= 5000.0`
- `"laptops under 1.5 lakh"` $\rightarrow$ Searches `laptops` with `price <= 150000.0`
- `"smartwatch under 15k"` $\rightarrow$ Searches `smartwatch` with `price <= 15000.0`
- Supports Indian numbering (`1,20,000`), Western numbering (`120,000`), Lakhs, Crores, and currency symbols (`₹`, `$`, `€`, `£`, `rs`).

### 2. Bidirectional Synonyms & Typo Tolerance
- Powered by a custom Elasticsearch analyzer (`product_synonym_analyzer`) configured with `english_stop`, `english_stemmer`, and centralized synonyms from `config/synonyms.py`.
- Searching `"cell phone"` automatically matches `"smartphone"`, `"iPhone"`, or `"mobile"`.
- Native typo tolerance (`fuzziness: "AUTO"`) handles common spelling mistakes (e.g., `"samsng"` $\rightarrow$ `"Samsung"`).

### 3. Dynamic Faceted Filtering & Harmonization
- **Strict Active Filter**: Only active products (`is_active: true`) are displayed and counted.
- **Bi-directional Scoped Brands**: Selecting a category automatically filters the brand dropdown to only show brands available in that category.
- **Mismatch Protection**: Automatically prevents impossible filter combinations (e.g., selecting `Footwear` and brand `Dell` automatically resets the brand).

### 4. Interactive 3-Tab Frontend
- **🛍️ Product Cards View**: E-commerce card grid with prices, ratings, categories, and brand tags.
- **⚡ Raw Elasticsearch JSON**: Syntax-highlighted dark-theme JSON response payload.
- **🔍 Elasticsearch Query**: Live inspection tab displaying the exact Elasticsearch Query DSL generated for the user's search.
- **One-Click Copy**: Dynamically copies either the response JSON or the Query DSL to your clipboard.

---

## ⚙️ Installation & Setup

### 1. Prerequisites
- Python 3.10+
- Microsoft SQL Server with `ODBC Driver 17 for SQL Server`
- Elasticsearch 8.x running locally or remotely

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your database and Elasticsearch credentials:
```ini
# SQL Server
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_SERVER=localhost
DB_NAME=vansh
DB_TABLE=dbo.products
DB_USER=your_user
DB_PASSWORD=your_password
DB_PRIMARY_KEY=product_id
DB_TIMESTAMP_COL=updated_at

# Elasticsearch
ES_HOST=https://localhost:9200
ES_INDEX=products_from_ssms
ES_USER=elastic
ES_PASSWORD=your_password
ES_BATCH_SIZE=1000
```

---

## 🔄 Running the ETL Sync Pipeline

Extract records from SQL Server and bulk index them into Elasticsearch:

```bash
python sync_pipeline.py
```

- **Incremental Sync (Default)**: If `sync_state.json` contains a checkpoint date, it automatically syncs only newly added or modified products.
- **Full Re-Sync**: Simply delete or clear `sync_state.json` to extract all records from scratch.
- **Rebuilding Index**: Set `recreate_index=True` inside `sync_pipeline.py` to rebuild index mapping and synonyms:
  ```python
  run_products_sync(recreate_index=True)
  ```

---

## 🚀 Running the FastAPI Search Server

Start the API with Uvicorn auto-reload:

```bash
uvicorn api.main:app --reload --port 8000
```

- **API Base URL**: `http://localhost:8000`
- **Interactive Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc UI**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🌐 API Reference

### `GET /search`

Searches products with full-text scoring, price intent extraction, dynamic facets, sorting, and pagination.

#### Query Parameters:
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `q` | `string` | `null` | Search query (e.g. `'mobile phones under 1,20,000'`, `'shoes 15k'`) |
| `category` | `string` | `null` | Exact category filter (e.g. `'Electronics'`, `'Footwear'`) |
| `brand` | `string` | `null` | Exact brand filter (e.g. `'Nike'`, `'Samsung'`, `'Dell'`) |
| `min_price` | `float` | `null` | Explicit minimum price filter |
| `max_price` | `float` | `null` | Explicit maximum price filter |
| `sort_by` | `string` | `'relevance'` | `'relevance'`, `'price_asc'`, `'price_desc'`, `'rating_desc'`, `'name_asc'` |
| `page` | `integer` | `1` | Page number (1-indexed) |
| `size` | `integer` | `10` | Results per page (1 to 50) |

#### Example Request:
```http
GET http://localhost:8000/search?q=phones+under+15000&sort_by=price_asc&page=1&size=10
```

#### Example Response:
```json
{
  "total_records": 42,
  "page": 1,
  "size": 10,
  "filters_applied": {
    "search_term": "phones",
    "min_price": null,
    "max_price": 15000.0,
    "category": "Electronics",
    "brand": null,
    "sort_by": "price_asc"
  },
  "available_categories": ["Electronics"],
  "available_brands": ["Motorola", "Realme", "Redmi", "Samsung"],
  "elasticsearch_query": {
    "query": {
      "bool": {
        "must": [{ "multi_match": { "query": "phones", "operator": "and", "fuzziness": "AUTO" } }],
        "filter": [{ "term": { "is_active": true } }, { "range": { "price": { "lte": 15000.0 } } }]
      }
    }
  },
  "products": [
    {
      "product_id": 1042,
      "product_name": "Samsung Galaxy M14 5G",
      "category": "Electronics",
      "brand": "Samsung",
      "price": 12499.0,
      "rating": 4.2,
      "is_active": true
    }
  ]
}
```

---

## 🧪 Running Automated Unit Tests

The test suite validates numeric conversion, Indian currency units, natural language price parsing, Elasticsearch query generation, and facet harmonization:

```bash
python -m unittest tests/test_search.py
```

---

## 💻 Frontend Usage

Simply open [frontend/index.html](file:///d:/OneDrive%20-%20Rysun%20Labs/Desktop/ES_Project/frontend/index.html) in any modern web browser or serve it via Live Server:
- Interactive searchbar with natural language price support.
- Category & Brand dynamic dropdowns that auto-synchronize with search results.
- Switch between **🛍️ Product Cards**, **⚡ Raw JSON**, and **🔍 Elasticsearch Query** with single-click copying.
