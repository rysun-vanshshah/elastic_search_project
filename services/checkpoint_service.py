# ==============================================================================
# CHECKPOINT SERVICE (services/checkpoint_service.py)
# Reads and saves sync checkpoints in sync_state.json to enable incremental sync
# ==============================================================================

import os
import json
from typing import Optional, Dict, Any
from config.logger import get_logger

logger = get_logger("CheckpointService")


class CheckpointService:
    """
    Manages reading and writing sync checkpoints to sync_state.json.
    Helps the pipeline remember the last synced timestamp or product_id.
    """

    def __init__(self, filepath: str = "sync_state.json"):
        self.filepath = filepath

    def load_state(self) -> Dict[str, Any]:
        """Reads the sync state JSON file. Returns {} if the file does not exist."""
        if not os.path.exists(self.filepath):
            return {}

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading checkpoint file '{self.filepath}': {e}")
            return {}

    def get_last_checkpoint(self, key_name: str = "updated_at") -> Optional[str]:
        """Returns the saved checkpoint value (e.g. last timestamp or ID), or None."""
        state = self.load_state()
        return state.get(key_name)

    def save_checkpoint(self, last_value: Any, key_name: str = "updated_at") -> None:
        """Saves the latest checkpoint value into sync_state.json."""
        if last_value is None:
            return

        state = self.load_state()

        # Convert date/datetime objects to ISO string format (e.g. 2026-09-30T10:29:43)
        state[key_name] = last_value.isoformat() if hasattr(last_value, "isoformat") else str(last_value)

        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=4)
            logger.info(f"Saved checkpoint: {key_name} = {state[key_name]}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint to '{self.filepath}': {e}")
