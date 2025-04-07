"""
Stiebel Eltron Heat Pump Control - Main Application
"""
import os
import sys
import time
import logging
import signal
import yaml
from typing import Dict, Any, Optional, List, Set, Tuple, Union

from stiebel_control.can_interface import CanInterface
from stiebel_control.mqtt_interface import MqttInterface
from stiebel_control.config_manager import ConfigManager
from stiebel_control.entity_manager import EntityManager
from stiebel_control.signal_processor import SignalProcessor
from stiebel_control.utils.logging_utils import configure_logging

logger = logging.getLogger(__name__)

class StiebelControl:
    """
    Main controller class for the Stiebel Eltron Heat Pump Control.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the controller.
        
        Args:
            config_path: Path to the service configuration file
        """
        # Load configuration
        self.config_manager = ConfigManager(config_path)
        
        # Configure logging
        configure_logging(self.config_manager.get_logging_config())
        
        # Initialize interfaces
        self._init_can_interface()
        self._init_mqtt_interface()
        
        # Initialize entity management and signal processing
        self.entity_manager = EntityManager(self.mqtt_interface, self.config_manager)
        self.signal_processor = SignalProcessor(
            self.entity_manager,
            self.mqtt_interface,
            self.can_interface,
            self.config_manager
        )
        
        # Set up callbacks
        self._setup_callbacks()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Stiebel Control initialized")
        
    def _init_can_interface(self) -> None:
        """
        Initialize the CAN interface.
        """
        can_config = self.config_manager.get_can_config()
        interface_name = can_config.get('interface', 'can0')
        bitrate = can_config.get('bitrate', 20000)
        
        try:
            logger.info(f"Initializing CAN interface {interface_name} at {bitrate} bps")
            # We'll initialize the CAN interface without a callback first
            # and set it later after signal_processor is initialized
            self.can_interface = CanInterface(
                can_interface=interface_name,
                bitrate=bitrate
            )
        except Exception as e:
            logger.error(f"Failed to initialize CAN interface: {e}")
            sys.exit(1)
            
    def _init_mqtt_interface(self) -> None:
        """
        Initialize the MQTT interface.
        """
        mqtt_config = self.config_manager.get_mqtt_config()
        
        try:
            logger.info(f"Initializing MQTT interface to {mqtt_config.get('host')}:{mqtt_config.get('port')}")
            self.mqtt_interface = MqttInterface(
                host=mqtt_config.get('host', 'localhost'),
                port=mqtt_config.get('port', 1883),
                username=mqtt_config.get('username'),
                password=mqtt_config.get('password'),
                client_id=mqtt_config.get('client_id', 'stiebel_control'),
                discovery_prefix=mqtt_config.get('discovery_prefix', 'homeassistant'),
                base_topic=mqtt_config.get('base_topic', 'stiebel_control')
            )
            
            # Connect to the MQTT broker immediately 
            # This ensures we're connected before any entities are registered
            if not self.mqtt_interface.connect():
                logger.warning("Failed to connect to MQTT broker, will retry during startup")
                
        except Exception as e:
            logger.error(f"Failed to initialize MQTT interface: {e}")
            sys.exit(1)
            
    def _setup_callbacks(self) -> None:
        """
        Set up callbacks between components.
        """
        # Set the callback for the CAN interface
        # The CAN interface doesn't have a register_callback method,
        # so we need to set the callback attribute directly
        self.can_interface.callback = self.signal_processor.process_signal
        
        # Set the MQTT command callback
        # The MqttInterface uses a direct attribute rather than a setter method
        self.mqtt_interface.command_callback = self.signal_processor.handle_command
        
        logger.debug("Callbacks set up")
        
    def start(self) -> None:
        """
        Start the controller.
        """
        logger.info("Starting Stiebel Control")
        
        try:
            # Ensure MQTT is connected
            if hasattr(self, 'mqtt_interface') and not self.mqtt_interface.connected:
                logger.info("Connecting to MQTT broker...")
                self.mqtt_interface.connect()
                
            # Connect to the CAN bus
            if hasattr(self, 'can_interface'):
                self.can_interface.start()
                
            # Build entity mapping
            self.entity_manager.build_entity_mapping(self.can_interface)
            
            # Start update loop
            self._update_loop()
            
        except Exception as e:
            logger.error(f"Error in controller: {e}")
            self.stop()
            
    def stop(self) -> None:
        """
        Stop the controller and clean up resources.
        """
        logger.info("Stopping Stiebel Control")
        
        try:
            if hasattr(self, 'mqtt_interface'):
                self.mqtt_interface.disconnect()
                
            if hasattr(self, 'can_interface'):
                self.can_interface.stop()
                
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            
    def _update_loop(self) -> None:
        """
        Main update loop.
        """
        update_interval = self.config_manager.get_update_interval()
        logger.info(f"Starting update loop with interval of {update_interval} seconds")
        
        try:
            while True:
                # The CAN interface is already sending updates asynchronously
                # via the callback. This loop can be used for periodic tasks
                # like polling values that don't automatically update.
                
                # Process any pending updates
                time.sleep(update_interval)
                
        except KeyboardInterrupt:
            logger.info("Update loop interrupted by user")
            self.stop()
            
        except Exception as e:
            logger.error(f"Error in update loop: {e}")
            self.stop()
            
    def _signal_handler(self, sig, frame) -> None:
        """
        Handle signals for graceful shutdown.
        """
        logger.info(f"Received signal {sig}, shutting down")
        self.stop()
        sys.exit(0)

def main():
    """
    Main entry point.
    """
    # Default configuration path
    config_path = os.environ.get(
        'STIEBEL_CONFIG_PATH', 
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'service_config.yaml')
    )
    
    # Allow overriding config path from command line
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        
    # Create and start the controller
    controller = StiebelControl(config_path)
    controller.start()

if __name__ == "__main__":
    main()
