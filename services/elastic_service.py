# ==============================================================================
# ELASTICSEARCH SERVICE (services/elastic_service.py)
# Handles Elasticsearch connection, index schema with analyzers, and bulk ingestion
# ==============================================================================

from typing import List, Dict, Any, Tuple, Optional
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from config.settings import Settings
from config.synonyms import PRODUCT_SYNONYMS
from config.logger import get_logger

logger = get_logger("ElasticService")


class ElasticService:
    """
    Manages Elasticsearch connection, product index setup, and bulk indexing.
    Provides natural language search support with synonyms, stemming, and stopwords.
    """

    # --------------------------------------------------------------------------
    # 1. TEXT ANALYSIS CONFIGURATION
    # - english_stop:    Ignores common filler words (a, the, is, of)
    # - english_stemmer: Normalizes plurals and verbs (shoes -> shoe, running -> run)
    # - product_synonyms: Expands equivalent terms (phone <-> mobile <-> smartphone)
    # --------------------------------------------------------------------------
    PRODUCT_INDEX_SETTINGS = {
        "analysis": {
            "filter": {
                "english_stop": {
                    "type": "stop",
                    "stopwords": "_english_"
                },
                "english_stemmer": {
                    "type": "stemmer",
                    "language": "english"
                },
                "product_synonyms": {
                    "type": "synonym",
                    "synonyms": PRODUCT_SYNONYMS
                }
            },
            "analyzer": {
                "product_synonym_analyzer": {
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "english_stop",
                        "product_synonyms",
                        "english_stemmer"
                    ]
                }
            }
        }
    }

    # --------------------------------------------------------------------------
    # 2. FIELD DATA MAPPINGS (Matches dbo.products table)
    # - text:    Full-text searchable with synonyms and typo tolerance
    # - keyword: Exact matching for dropdown filters and aggregations (brand, city)
    # - numbers: Integer and float types for price filtering and sorting
    # --------------------------------------------------------------------------
    PRODUCT_INDEX_MAPPINGS = {
        "properties": {
            "product_id": {"type": "integer"},
            "product_name": {
                "type": "text",
                "analyzer": "product_synonym_analyzer",
                "search_analyzer": "product_synonym_analyzer",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
            },
            "category": {
                "type": "text",
                "analyzer": "product_synonym_analyzer",
                "search_analyzer": "product_synonym_analyzer",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
            },
            "brand": {"type": "keyword"},
            "description": {
                "type": "text",
                "analyzer": "product_synonym_analyzer",
                "search_analyzer": "product_synonym_analyzer"
            },
            "price": {"type": "float"},
            "rating": {"type": "float"},
            "stock": {"type": "integer"},
            "city": {"type": "keyword"},
            "gender": {"type": "keyword"},
            "is_active": {"type": "boolean"},
            "created_at": {
                "type": "date",
                "format": "yyyy-MM-dd||strict_date_optional_time||epoch_millis"
            },
            "updated_at": {
                "type": "date",
                "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd'T'HH:mm:ss||strict_date_optional_time||epoch_millis"
            }
        }
    }

    def __init__(
        self,
        host: Optional[str] = None,
        index_name: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.host = host or Settings.ES_HOST
        self.index_name = (index_name or Settings.ES_INDEX).lower()
        self.username = username or Settings.ES_USER
        self.password = password or Settings.ES_PASSWORD
        self.api_key = api_key or Settings.ES_API_KEY
        self.client: Optional[Elasticsearch] = None

    def connect(self) -> None:
        """Connects to the Elasticsearch cluster and validates connectivity."""
        try:
            logger.info(f"Connecting to Elasticsearch at '{self.host}'...")
            kwargs: Dict[str, Any] = {"hosts": [self.host]}

            # Disable SSL certificate verification for local HTTPS setups
            if self.host.lower().startswith("https://"):
                kwargs["verify_certs"] = False

            if self.api_key:
                kwargs["api_key"] = self.api_key
            elif self.username and self.password:
                kwargs["basic_auth"] = (self.username, self.password)

            self.client = Elasticsearch(**kwargs)

            if self.client.ping():
                logger.info("Connected to Elasticsearch successfully.")
            else:
                logger.warning("Elasticsearch server did not respond to ping.")

        except Exception as e:
            err_text = str(e)
            if "ConnectionRefused" in err_text or "Failed to establish a new connection" in err_text:
                friendly_err = (
                    f"Could not connect to Elasticsearch at '{self.host}'. "
                    "Please ensure your Elasticsearch service is running or check ES_HOST in your .env file."
                )
            elif "security_exception" in err_text or "401" in err_text or "Unauthorized" in err_text:
                friendly_err = (
                    "Elasticsearch authentication failed. Please verify ES_USER, ES_PASSWORD, or ES_API_KEY in your .env file."
                )
            else:
                friendly_err = f"Elasticsearch connection error: {e}"
            logger.error(friendly_err)
            raise RuntimeError(friendly_err) from None

    def setup_products_index(self, recreate: bool = False) -> None:
        """
        Creates the 'products' index with analyzer settings and mappings if it does not exist.
        If recreate=True, deletes the existing index first to apply fresh settings.
        """
        if not self.client:
            self.connect()

        try:
            if recreate and self.client.indices.exists(index=self.index_name):
                logger.info(f"Recreating Elasticsearch index '{self.index_name}'...")
                self.client.indices.delete(index=self.index_name)

            if not self.client.indices.exists(index=self.index_name):
                logger.info(f"Creating Elasticsearch index '{self.index_name}' with analyzers and synonyms...")
                self.client.indices.create(
                    index=self.index_name,
                    settings=self.PRODUCT_INDEX_SETTINGS,
                    mappings=self.PRODUCT_INDEX_MAPPINGS
                )
                logger.info(f"Index '{self.index_name}' created successfully.")
            else:
                logger.info(f"Index '{self.index_name}' is ready.")
        except Exception as e:
            friendly_err = f"Failed to setup Elasticsearch index '{self.index_name}': {e}"
            logger.error(friendly_err)
            raise RuntimeError(friendly_err) from None

    def bulk_insert_products(
        self,
        products: List[Dict[str, Any]],
        doc_id_field: str = "product_id"
    ) -> Tuple[int, int]:
        """
        Bulk indexes a batch of products into Elasticsearch.
        Uses product_id as the document ID to ensure deduplication.
        """
        if not self.client:
            self.connect()

        if not products:
            logger.info("No records to index.")
            return 0, 0

        # Build bulk insert actions with deduplication on product_id
        actions = []
        for doc in products:
            action = {"_index": self.index_name, "_source": doc}
            if doc.get(doc_id_field) is not None:
                action["_id"] = str(doc[doc_id_field])
            actions.append(action)

        try:
            success_count, errors = bulk(
                self.client,
                actions,
                raise_on_error=False,
                stats_only=False
            )

            failed_count = len(errors) if isinstance(errors, list) else 0
            if failed_count > 0:
                logger.warning(f"Bulk insert had {failed_count} errors.")
                for err in errors[:3]:
                    logger.error(f"Error detail: {err}")
            else:
                logger.info(f"Successfully inserted {success_count} products into '{self.index_name}'.")

            return success_count, failed_count

        except Exception as e:
            friendly_err = f"Bulk insert failed for index '{self.index_name}': {e}"
            logger.error(friendly_err)
            raise RuntimeError(friendly_err) from None

    def search(self, **kwargs) -> Dict[str, Any]:
        """
        Executes a search query against Elasticsearch.
        Defaults to the configured index if 'index' is omitted.
        """
        if not self.client:
            self.connect()

        if "index" not in kwargs:
            kwargs["index"] = self.index_name

        return self.client.search(**kwargs)
