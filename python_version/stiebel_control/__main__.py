"""
Main entry point for the stiebel_control package.

This file allows running the package with python -m stiebel_control
"""

import sys
import logging
import argparse
from stiebel_control.main import StiebelControl

logger = logging.getLogger("stiebel_control.__main__")

def main():
    """Main entry point for the stiebel_control package when run as a module."""
    parser = argparse.ArgumentParser(description='Stiebel Eltron heat pump control')
    parser.add_argument('--config', dest='config_file', 
                        default='service_config.yaml',
                        help='Path to configuration file')
    args = parser.parse_args()
    
    # Initialize and start the application
    app = StiebelControl(args.config_file)
    
    # Start the application
    try:
        app.start()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)
    finally:
        # Ensure proper cleanup
        app.stop()
        
    sys.exit(0)

if __name__ == "__main__":
    main()
