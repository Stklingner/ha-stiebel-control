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
                        default='config.yaml',
                        help='Path to configuration file')
    args = parser.parse_args()
    
    # Initialize and start the application
    app = StiebelControl(args.config_file)
    
    # Explicitly start the application
    if app.start():
        try:
            # Run until interrupted
            logger.info("Stiebel Control running, press Ctrl+C to stop")
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            app.stop()
    else:
        logger.error("Failed to start application")
        sys.exit(1)

if __name__ == '__main__':
    main()
