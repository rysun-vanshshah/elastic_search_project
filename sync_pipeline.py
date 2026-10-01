# ==============================================================================
# MAIN SYNC PIPELINE (sync_pipeline.py)
# 
# Purpose:
# This script extracts product data from Microsoft SQL Server (database: vansh,
# table: dbo.products) and loads it into Elasticsearch (index: products_from_ssms).
#
# Sync Modes:
# 1. Full Sync:
#    Copies all products from SQL Server to Elasticsearch from scratch.
# 2. Incremental Sync (Default):
#    Reads the last saved checkpoint (e.g. last 'updated_at' timestamp) and only
#    syncs products that were added or modified after that time.
# ==============================================================================

# Project imports
from config.settings import Settings
from config.logger import get_logger
from services.checkpoint_service import CheckpointService
from services.sql_service import SQLService
from services.elastic_service import ElasticService

# Initialize configured logger with clean timestamp formatting
logger = get_logger("SyncPipeline")


# ==============================================================================
# MAIN SYNC FUNCTION
# ==============================================================================
def run_products_sync(recreate_index: bool = False) -> None:
    """
    Coordinates the entire ETL process:
    SQL Server -> Read Batches -> Bulk Insert -> Elasticsearch -> Save Checkpoint

    Parameters:
        recreate_index (bool): If True, deletes the old Elasticsearch index and creates
                               a fresh one with the latest analyzers and synonyms.
    """
    print("\n" + "=" * 65)
    print("STARTING ETL SYNC: SQL SERVER -> ELASTICSEARCH")
    print("=" * 65)

    # --------------------------------------------------------------------------
    # STEP 1: INITIALIZE CHECKPOINT SERVICE
    # The checkpoint service reads 'sync_state.json' to see where the last sync stopped.
    # --------------------------------------------------------------------------
    checkpoint_service = CheckpointService(filepath=Settings.STATE_FILE)
    
    # Decide which column to track:
    # Uses 'updated_at' if provided in .env, otherwise falls back to 'product_id'
    tracking_col = (
        Settings.DB_TIMESTAMP_COL 
        if (Settings.DB_TIMESTAMP_COL and Settings.DB_TIMESTAMP_COL.strip()) 
        else Settings.DB_PRIMARY_KEY
    )
    
    # If recreating index, start fresh; otherwise read checkpoint from sync_state.json
    last_checkpoint = None if recreate_index else checkpoint_service.get_last_checkpoint(key_name=tracking_col)

    # Inform the user which sync mode is active
    if last_checkpoint:
        logger.info(f"Mode: INCREMENTAL SYNC (Only fetching rows where {tracking_col} > '{last_checkpoint}')")
    else:
        logger.info("Mode: FULL SYNC (Extracting all records from database)")

    # --------------------------------------------------------------------------
    # STEP 2: CREATE DATABASE AND ELASTICSEARCH SERVICE INSTANCES
    # --------------------------------------------------------------------------
    sql_service = SQLService(
        connection_string=Settings.get_sql_connection_string(),
        table_name=Settings.DB_TABLE
    )

    elastic_service = ElasticService(
        host=Settings.ES_HOST,
        index_name=Settings.ES_INDEX,
        username=Settings.ES_USER,
        password=Settings.ES_PASSWORD,
        api_key=Settings.ES_API_KEY
    )

    # Counters to track progress
    total_indexed = 0
    total_failed = 0
    latest_checkpoint_val = last_checkpoint

    try:
        # Connect to SQL Server and Elasticsearch
        sql_service.connect()
        elastic_service.connect()

        # Ensure index exists with correct schema, synonyms, and token filters
        # If recreate_index is True, it deletes and rebuilds the index first
        elastic_service.setup_products_index(recreate=recreate_index)

        # ----------------------------------------------------------------------
        # STEP 3: STREAM PRODUCTS IN BATCHES FROM SQL SERVER
        # Uses a generator so we don't load all 10,000+ records into RAM at once.
        # It reads chunks (e.g. 1,000 rows per batch) one at a time.
        # ----------------------------------------------------------------------
        batch_generator = sql_service.fetch_product_batches(
            primary_key=Settings.DB_PRIMARY_KEY,
            timestamp_col=Settings.DB_TIMESTAMP_COL,
            last_checkpoint=last_checkpoint,
            batch_size=Settings.ES_BATCH_SIZE
        )

        batch_number = 1
        for product_batch in batch_generator:
            if not product_batch:
                continue

            logger.info(f"Batch #{batch_number}: Processing {len(product_batch)} products...")
            
            # ------------------------------------------------------------------
            # STEP 4: BULK INSERT BATCH INTO ELASTICSEARCH
            # We pass doc_id_field='product_id' so Elasticsearch sets _id = product_id.
            # This ensures updating existing products overwrites them without duplicates.
            # ------------------------------------------------------------------
            success, failed = elastic_service.bulk_insert_products(
                products=product_batch,
                doc_id_field=Settings.DB_PRIMARY_KEY
            )

            total_indexed += success
            total_failed += failed

            # ------------------------------------------------------------------
            # STEP 5: SAVE PROGRESS CHECKPOINT
            # Read the last record of this batch and remember its timestamp or product_id.
            # If the sync is interrupted later, next run will resume from this point!
            # ------------------------------------------------------------------
            last_record = product_batch[-1]
            if tracking_col in last_record and last_record[tracking_col] is not None:
                latest_checkpoint_val = last_record[tracking_col]
                checkpoint_service.save_checkpoint(last_value=latest_checkpoint_val, key_name=tracking_col)

            batch_number += 1

        # ----------------------------------------------------------------------
        # STEP 6: PRINT FINAL SYNC SUMMARY
        # ----------------------------------------------------------------------
        print("\n" + "=" * 65)
        print("SYNC COMPLETED SUCCESSFULLY")
        print(f"Total Indexed Products : {total_indexed}")
        print(f"Total Failed Products  : {total_failed}")
        print(f"Last Checkpoint Saved  : {tracking_col} = {latest_checkpoint_val}")
        print("=" * 65 + "\n")

    except Exception as e:
        print("\n" + "=" * 65)
        print("SYNC PIPELINE STOPPED (ERROR)")
        print(f"Reason : {e}")
        print("=" * 65 + "\n")
        logger.error(f"Sync process could not complete: {e}")
    finally:
        # Always close the database connection cleanly, even if an error occurred
        sql_service.close()

# ==============================================================================
# SCRIPT ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    # Set recreate_index=True to rebuild the Elasticsearch index mapping and analyzers.
    run_products_sync(recreate_index=False)
