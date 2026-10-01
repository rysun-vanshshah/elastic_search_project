# ==============================================================================
# SQL SERVICE (services/sql_service.py)
# Connects to SQL Server database and extracts products records in batches
# ==============================================================================

import pyodbc
import decimal
import datetime
import uuid
from typing import List, Dict, Any, Generator, Optional
from config.logger import get_logger

logger = get_logger("SQLService")


class SQLService:
    """Extracts product records from SQL Server in batches and formats them for JSON."""

    def __init__(self, connection_string: str, table_name: str = "dbo.products"):
        self.connection_string = connection_string
        self.table_name = table_name
        self.connection = None

    def connect(self) -> None:
        """Connects to SQL Server database."""
        try:
            logger.info("Connecting to SQL Server database...")
            self.connection = pyodbc.connect(self.connection_string)
            logger.info("Successfully connected to SQL Server database.")
        except pyodbc.Error as e:
            err_text = str(e)
            if "08001" in err_text or "Login timeout" in err_text or "Error Locating Server" in err_text:
                friendly_err = (
                    "Could not reach SQL Server. Server is not accessible or connection timed out. "
                    "Please check if you are connected to the company VPN and the database server is running."
                )
            elif "28000" in err_text or "Login failed" in err_text:
                friendly_err = (
                    "SQL Server login failed. Please verify DB_USER and DB_PASSWORD credentials in your .env file."
                )
            elif "4060" in err_text or "Cannot open database" in err_text:
                friendly_err = (
                    "Cannot open the specified SQL Server database. Please verify DB_NAME in your .env file."
                )
            else:
                friendly_err = f"SQL Server database error: {e}"
            logger.error(friendly_err)
            raise RuntimeError(friendly_err) from None
        except Exception as e:
            friendly_err = f"Unexpected database connection error: {e}"
            logger.error(friendly_err)
            raise RuntimeError(friendly_err) from None

    def close(self) -> None:
        """Closes SQL Server connection."""
        if self.connection:
            self.connection.close()
            logger.info("SQL Server connection closed.")

    @staticmethod
    def _format_cell(val: Any) -> Any:
        """Formats SQL data types (Decimal, datetime, UUID, bytes) for Elasticsearch JSON."""
        if isinstance(val, decimal.Decimal):
            return float(val)
        if hasattr(val, "isoformat"):
            return val.isoformat()
        if isinstance(val, uuid.UUID):
            return str(val)
        if isinstance(val, bytes):
            return val.hex()
        return val

    def fetch_product_batches(
        self,
        primary_key: str = "product_id",
        timestamp_col: Optional[str] = None,
        last_checkpoint: Optional[str] = None,
        batch_size: int = 1000
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """Fetches product records from SQL Server in batches of 1,000."""
        if not self.connection:
            self.connect()

        cursor = self.connection.cursor()
        filter_col = timestamp_col if (timestamp_col and timestamp_col.strip()) else primary_key
        
        where_clause = ""
        params = []

        if last_checkpoint:
            where_clause = f"WHERE {filter_col} > ?"
            try:
                param_val = datetime.datetime.fromisoformat(str(last_checkpoint).replace("Z", ""))
            except (ValueError, TypeError):
                param_val = str(last_checkpoint).replace("T", " ")
            params.append(param_val)

        query = f"SELECT * FROM {self.table_name} {where_clause} ORDER BY {filter_col} ASC"
        logger.info(f"Querying SQL Server table '{self.table_name}'...")
        cursor.execute(query, params)

        columns = [col[0] for col in cursor.description]

        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            yield [
                {col: self._format_cell(val) for col, val in zip(columns, row)}
                for row in rows
            ]

        cursor.close()
