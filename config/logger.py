# ==============================================================================
# CENTRALIZED LOGGER CONFIGURATION (config/logger.py)
# 
# Purpose:
# Configures unified logging for all services, pipelines, and APIs in the project.
# Formats log messages with timestamps: [HH:MM:SS] Message
# Suppresses verbose third-party HTTP transport logs and SSL warnings.
#
# Usage:
#   from config.logger import get_logger
#   logger = get_logger("MyServiceName")
#   logger.info("Hello world")
# ==============================================================================

import sys
import logging
import warnings
import urllib3

# ------------------------------------------------------------------------------
# 1. SUPPRESS SSL WARNINGS & THIRD-PARTY TRANSPORT NOISE
# ------------------------------------------------------------------------------
warnings.filterwarnings("ignore")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Silence noisy HTTP connection logs from Elasticsearch and urllib3
logging.getLogger("elastic_transport").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# ------------------------------------------------------------------------------
# 2. CONFIGURE BASE ROOT LOGGER
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True  # Ensures this configuration applies even if another module imported logging earlier
)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger instance for the given module or service name.

    Example:
        logger = get_logger("SQLService")
        logger.info("Connected to database")
    """
    return logging.getLogger(name)
