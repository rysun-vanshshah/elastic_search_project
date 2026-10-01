# ==============================================================================
# CONFIGURATION SETTINGS (config/settings.py)
# Loads database, elasticsearch, and tracking configuration from .env file
# ==============================================================================

import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

class Settings:
    # --- SQL Server Settings ---
    DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
    DB_SERVER = os.getenv("DB_SERVER", "localhost")
    DB_PORT = os.getenv("DB_PORT", "1433")
    DB_NAME = os.getenv("DB_NAME", "vansh")
    DB_TABLE = os.getenv("DB_TABLE", "dbo.products")
    DB_USER = os.getenv("DB_USER", "vansh.shah")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    
    # Primary Key for product tracking (product_id)
    DB_PRIMARY_KEY = os.getenv("DB_PRIMARY_KEY", "product_id")
    # Optional Timestamp Column (leave empty if using product_id for incremental sync)
    DB_TIMESTAMP_COL = os.getenv("DB_TIMESTAMP_COL", "")

    # --- Elasticsearch Settings ---
    ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
    ES_INDEX = os.getenv("ES_INDEX", "products")
    ES_USER = os.getenv("ES_USER", "elastic")
    ES_PASSWORD = os.getenv("ES_PASSWORD", "")
    ES_API_KEY = os.getenv("ES_API_KEY", None)
    ES_BATCH_SIZE = int(os.getenv("ES_BATCH_SIZE", "1000"))

    # --- Sync Checkpoint File ---
    STATE_FILE = os.getenv("STATE_FILE", "sync_state.json")

    @classmethod
    def get_sql_connection_string(cls) -> str:
        """Generates pyodbc connection string for SQL Server Authentication."""
        server_spec = f"{cls.DB_SERVER},{cls.DB_PORT}" if (cls.DB_PORT and cls.DB_PORT.strip()) else cls.DB_SERVER
        return (
            f"DRIVER={{{cls.DB_DRIVER}}};"
            f"SERVER={server_spec};"
            f"DATABASE={cls.DB_NAME};"
            f"UID={cls.DB_USER};"
            f"PWD={cls.DB_PASSWORD};"
        )
