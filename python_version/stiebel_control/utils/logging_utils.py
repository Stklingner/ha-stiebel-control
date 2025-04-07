"""
Logging utilities for the Stiebel Control package.
"""
import logging
import os
import sys
from typing import Dict, Any

def configure_logging(config: Dict[str, Any]) -> None:
    """
    Configure logging based on provided configuration.
    
    Args:
        config: Logging configuration dictionary containing 'level'
    """
    level = config.get('level', 'INFO').upper()
    log_level = getattr(logging, level, logging.INFO)
    
    # Configure the root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.debug(f"Logging configured with level: {level}")
