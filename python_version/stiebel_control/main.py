"""
Main module for the Stiebel Eltron heat pump control application.

This module ties together the CAN interface and MQTT interface, handling
command processing and value updates.
"""

import os
import logging
import argparse
import time
import threading
import json
import yaml
from typing import Dict, Any, Optional

from stiebel_control.can_interface import CanInterface
from stiebel_control.mqtt_interface import MqttInterface
from stiebel_control.elster_table import (
    get_elster_index_by_name,
    get_elster_index_by_english_name,
    ElsterType
)

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StiebelControl:
    """
    Main application class for Stiebel Eltron heat pump control.
    
    This class handles the integration between the CAN bus and MQTT,
    including automatic Home Assistant discovery and periodic updates.
    """
    
    def __init__(self, config_file: str):
        """
        Initialize the application.
        
        Args:
            config_file: Path to the configuration file
        """
        self.config_file = config_file
        self.config = self._load_config()
        
        # Set up logging level from config
        log_level = self.config.get('logging', {}).get('level', 'INFO')
        logging.getLogger().setLevel(log_level)
        
        # Extract configuration values
        can_config = self.config.get('can', {})
        mqtt_config = self.config.get('mqtt', {})
        
        logger.info(f"Loading CAN configuration from {self.config_file}")
        logger.debug(f"CAN configuration: {can_config}")
        
        # Initialize CAN interface
        self.can_interface = CanInterface(
            can_interface=can_config.get('interface', 'can0'),
            bitrate=can_config.get('bitrate', 20000),
            callback=self._can_value_update_callback
        )
        
        logger.info(f"Loading MQTT configuration from {self.config_file}")
        logger.debug(f"MQTT configuration: {mqtt_config}")
        
        # Initialize MQTT interface
        logger.info(f"Initializing MQTT interface with host: {mqtt_config.get('host', 'localhost')}")
        self.mqtt_interface = MqttInterface(
            host=mqtt_config.get('host', 'localhost'),
            port=mqtt_config.get('port', 1883),
            username=mqtt_config.get('username'),
            password=mqtt_config.get('password'),
            client_id=mqtt_config.get('client_id', 'stiebel_control'),
            discovery_prefix=mqtt_config.get('discovery_prefix', 'homeassistant'),
            base_topic=mqtt_config.get('base_topic', 'stiebel_control'),
            command_callback=self._mqtt_command_callback
        )
        
        # Connect to MQTT broker
        logger.info("Attempting to connect to MQTT broker...")
        mqtt_connected = self.mqtt_interface.connect()
        if mqtt_connected:
            logger.info("Successfully connected to MQTT broker")
        else:
            logger.error("Failed to connect to MQTT broker, continuing without MQTT functionality")
            
        # Value cache
        self.value_cache = {}
        
        # Register known signals - do this at initialization to ensure entities are registered
        logger.info("Registering entities with Home Assistant during initialization")
        self.registered_entities = set()
        self._register_entities()
        
        # Thread for updating values
        self.update_thread = None
        self.running = False
        
    def _load_config(self) -> Dict:
        """
        Load the configuration from file.
        
        Returns:
            Dict: Configuration dictionary
        """
        try:
            if not os.path.exists(self.config_file):
                logger.error(f"Configuration file {self.config_file} not found")
                return {}
            
            with open(self.config_file, 'r') as f:
                if self.config_file.endswith('.yaml') or self.config_file.endswith('.yml'):
                    config = yaml.safe_load(f)
                elif self.config_file.endswith('.json'):
                    config = json.load(f)
                else:
                    logger.error(f"Unsupported configuration file format: {self.config_file}")
                    return {}
                
            logger.info(f"Loaded configuration from {self.config_file}")
            return config
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return {}
            
    def start(self) -> bool:
        """
        Start the application.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        logger.info("Starting Stiebel Control application")
        
        # Start CAN interface
        logger.info("Starting CAN interface")
        if not self.can_interface.start():
            logger.error("Failed to start CAN interface")
            return False
        logger.info("CAN interface started successfully")
            
        # Start MQTT interface
        logger.info("Connecting to MQTT broker")
        if not self.mqtt_interface.connect():
            logger.error("Failed to connect to MQTT broker")
            self.can_interface.stop()
            return False
        logger.info("MQTT broker connected successfully")
            
        # Start update thread
        logger.info("Starting update thread")
        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
        logger.info("Update thread started")
        
        logger.info("Stiebel Control started successfully")
        
        # Request an initial refresh of all values
        logger.info("Requesting initial value refresh")
        self._refresh_all_entities()
        
        return True
        
    def stop(self):
        """Stop the application."""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)
            
        self.mqtt_interface.disconnect()
        self.can_interface.stop()
        
        logger.info("Stiebel Control stopped")
        
    def _register_entities(self):
        """Register entities with Home Assistant via MQTT discovery."""
        entities_config = self.config.get('entities', {})
        
        logger.info(f"Starting entity registration with Home Assistant")
        
        # Register sensors
        for sensor_id, sensor_config in entities_config.get('sensors', {}).items():
            logger.debug(f"Registering sensor {sensor_id}")
            
            # Get signal definition
            signal_name = sensor_config.get('signal')
            if not signal_name:
                logger.warning(f"Sensor {sensor_id} has no signal name")
                continue
                
            # Register with MQTT
            logger.info(f"Registering sensor {sensor_id} for signal {signal_name}")
            registered = self.mqtt_interface.register_sensor(
                entity_id=sensor_id,
                name=sensor_config.get('name', sensor_id),
                device_class=sensor_config.get('device_class'),
                state_class=sensor_config.get('state_class'),
                unit_of_measurement=sensor_config.get('unit_of_measurement'),
                icon=sensor_config.get('icon')
            )
            
            if registered:
                logger.info(f"Successfully registered sensor {sensor_id}")
            else:
                logger.warning(f"Failed to register sensor {sensor_id}")
                
            # Add to registered entities
            self.registered_entities.add(sensor_id)
            
        # Register selects (for enum values)
        for select_id, select_config in entities_config.get('selects', {}).items():
            logger.debug(f"Registering select {select_id}")
            
            # Get signal definition
            signal_name = select_config.get('signal')
            if not signal_name:
                logger.warning(f"Select {select_id} has no signal name")
                continue
                
            # Register with MQTT
            logger.info(f"Registering select {select_id} for signal {signal_name}")
            registered = self.mqtt_interface.register_select(
                entity_id=select_id,
                name=select_config.get('name', select_id),
                options=select_config.get('options', []),
                icon=select_config.get('icon')
            )
            
            if registered:
                logger.info(f"Successfully registered select {select_id}")
            else:
                logger.warning(f"Failed to register select {select_id}")
                
            # Add to registered entities
            self.registered_entities.add(select_id)
            
        # Register buttons
        for button_id, button_config in entities_config.get('buttons', {}).items():
            logger.debug(f"Registering button {button_id}")
            
            # Register with MQTT
            logger.info(f"Registering button {button_id}")
            registered = self.mqtt_interface.register_button(
                entity_id=button_id,
                name=button_config.get('name', button_id),
                icon=button_config.get('icon')
            )
            
            if registered:
                logger.info(f"Successfully registered button {button_id}")
            else:
                logger.warning(f"Failed to register button {button_id}")
                
            # Add to registered entities
            self.registered_entities.add(button_id)
            
        logger.info(f"Registered {len(self.registered_entities)} entities with Home Assistant")
        
    def _update_loop(self):
        """Update loop for periodically polling values from the heat pump."""
        entities_config = self.config.get('entities', {})
        update_interval = self.config.get('update_interval', 60)  # Default: 60 seconds
        
        # Dictionary mapping entity IDs to CAN member indices and signal names
        entity_map = {}
        
        # Build entity map for sensors
        for sensor_id, sensor_config in entities_config.get('sensors', {}).items():
            signal_name = sensor_config.get('signal')
            can_member = sensor_config.get('can_member', 'PUMP')
            
            if signal_name:
                # Convert CAN member name to index
                member_index = self._get_can_member_index(can_member)
                if member_index is not None:
                    entity_map[sensor_id] = (member_index, signal_name)
        
        # Build entity map for selects
        for select_id, select_config in entities_config.get('selects', {}).items():
            signal_name = select_config.get('signal')
            can_member = select_config.get('can_member', 'PUMP')
            
            if signal_name:
                # Convert CAN member name to index
                member_index = self._get_can_member_index(can_member)
                if member_index is not None:
                    entity_map[select_id] = (member_index, signal_name)
        
        while self.running:
            try:
                # Request updates for all entities
                for entity_id, (member_index, signal_name) in entity_map.items():
                    self.can_interface.read_signal(member_index, signal_name)
                    
                    # Small delay between requests to avoid flooding the bus
                    time.sleep(0.1)
                    
                # Wait for the next update interval
                time.sleep(update_interval)
                
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                time.sleep(5)  # Wait a bit before retrying
                
    def _can_value_update_callback(self, signal_name: str, value: Any):
        """
        Callback for when a CAN value is updated.
        
        Args:
            signal_name: Name of the signal
            value: New value
        """
        logger.info(f"Received CAN value update for signal {signal_name}: {value}")
        
        # Find entities that use this signal and update them
        entities_config = self.config.get('entities', {})
        
        # Create a list of all configured signal names for easy debugging
        if not hasattr(self, '_signal_map_logged'):
            all_signals = set()
            for sensor_id, sensor_config in entities_config.get('sensors', {}).items():
                signal = sensor_config.get('signal')
                if signal:
                    all_signals.add(signal)
            for select_id, select_config in entities_config.get('selects', {}).items():
                signal = select_config.get('signal')
                if signal:
                    all_signals.add(signal)
            logger.info(f"Configured signals in config.yaml: {sorted(list(all_signals))}")
            self._signal_map_logged = True
        
        match_found = False
        
        # Check sensors
        for sensor_id, sensor_config in entities_config.get('sensors', {}).items():
            config_signal = sensor_config.get('signal')
            if config_signal == signal_name:
                match_found = True
                logger.info(f"Found matching sensor {sensor_id} for signal {signal_name}")
                # Apply any transformations if configured
                transformed_value = self._apply_transformation(value, sensor_config.get('transform'))
                
                # Update the cache
                self.value_cache[sensor_id] = transformed_value
                
                # Publish to MQTT
                logger.info(f"Publishing sensor {sensor_id} = {transformed_value} to MQTT")
                published = self.mqtt_interface.publish_state(sensor_id, transformed_value)
                if published:
                    logger.info(f"Successfully published {sensor_id} state")
                else:
                    logger.warning(f"Failed to publish {sensor_id} state")
                
        # Check selects
        for select_id, select_config in entities_config.get('selects', {}).items():
            config_signal = select_config.get('signal')
            if config_signal == signal_name:
                match_found = True
                logger.info(f"Found matching select {select_id} for signal {signal_name}")
                # Selects don't have transformations
                
                # Update the cache
                self.value_cache[select_id] = value
                
                # Publish to MQTT
                logger.info(f"Publishing select {select_id} = {value} to MQTT")
                published = self.mqtt_interface.publish_state(select_id, value)
                if published:
                    logger.info(f"Successfully published {select_id} state")
                else:
                    logger.warning(f"Failed to publish {select_id} state")
                
        if not match_found:
            logger.debug(f"No entity matches found for signal {signal_name}")
        
    def _mqtt_command_callback(self, entity_id: str, command: str):
        """
        Callback for when a command is received via MQTT.
        
        Args:
            entity_id: ID of the entity the command is for
            command: Command value
        """
        # Find the entity configuration
        entities_config = self.config.get('entities', {})
        
        # Check if this is a select command
        for select_id, select_config in entities_config.get('selects', {}).items():
            if select_id == entity_id:
                signal_name = select_config.get('signal')
                can_member = select_config.get('can_member', 'PUMP')
                
                if signal_name:
                    # Convert CAN member name to index
                    member_index = self._get_can_member_index(can_member)
                    if member_index is not None:
                        # Write the value to the heat pump
                        self.can_interface.write_signal(member_index, signal_name, command)
                        
                        # Update local cache
                        self.value_cache[select_id] = command
                        
                        # Also publish to state topic to confirm the change
                        self.mqtt_interface.publish_state(select_id, command)
                        
                return
                
        # Check if this is a button command
        for button_id, button_config in entities_config.get('buttons', {}).items():
            if button_id == entity_id:
                action = button_config.get('action')
                
                if action == 'refresh_all':
                    # Trigger a refresh of all entities
                    logger.info("Refreshing all entities")
                    self._refresh_all_entities()
                elif action == 'custom':
                    # Execute custom action
                    logger.info(f"Executing custom action for button {button_id}")
                    self._execute_custom_action(button_config.get('custom_action', {}))
                    
                return
                
        logger.warning(f"Received command for unknown entity: {entity_id}")
        
    def _get_can_member_index(self, can_member_name: str) -> Optional[int]:
        """
        Convert a CAN member name to its index.
        
        Args:
            can_member_name: Name of the CAN member
            
        Returns:
            int: Index of the CAN member, or None if not found
        """
        # This mapping should match the indices in CanInterface.DEFAULT_CAN_MEMBERS
        can_member_map = {
            "ESPCLIENT": CanInterface.CM_ESPCLIENT,
            "PUMP": CanInterface.CM_PUMP,
            "FE7X": CanInterface.CM_FE7X,
            "FEK": CanInterface.CM_FEK,
            "MANAGER": CanInterface.CM_MANAGER,
            "FE7": CanInterface.CM_FE7
        }
        
        return can_member_map.get(can_member_name.upper())
        
    def _apply_transformation(self, value: Any, transform: Optional[Dict]) -> Any:
        """
        Apply a transformation to a value.
        
        Args:
            value: Value to transform
            transform: Transformation configuration
            
        Returns:
            Any: Transformed value
        """
        if not transform:
            return value
            
        transform_type = transform.get('type')
        
        if transform_type == 'scale':
            # Scale the value by a factor
            factor = float(transform.get('factor', 1.0))
            offset = float(transform.get('offset', 0.0))
            return float(value) * factor + offset
            
        elif transform_type == 'map':
            # Map values to other values
            mapping = transform.get('mapping', {})
            return mapping.get(str(value), value)
            
        elif transform_type == 'formula':
            # Apply a formula (simple eval)
            formula = transform.get('formula', 'x')
            x = float(value)
            try:
                return eval(formula)
            except Exception as e:
                logger.error(f"Error evaluating formula {formula}: {e}")
                return value
                
        return value
        
    def _refresh_all_entities(self):
        """Request a refresh of all registered entities."""
        entities_config = self.config.get('entities', {})
        
        # Refresh sensors
        for sensor_id, sensor_config in entities_config.get('sensors', {}).items():
            signal_name = sensor_config.get('signal')
            can_member = sensor_config.get('can_member', 'PUMP')
            
            if signal_name:
                # Convert CAN member name to index
                member_index = self._get_can_member_index(can_member)
                if member_index is not None:
                    self.can_interface.read_signal(member_index, signal_name)
                    
                    # Small delay between requests
                    time.sleep(0.1)
                    
        # Refresh selects
        for select_id, select_config in entities_config.get('selects', {}).items():
            signal_name = select_config.get('signal')
            can_member = select_config.get('can_member', 'PUMP')
            
            if signal_name:
                # Convert CAN member name to index
                member_index = self._get_can_member_index(can_member)
                if member_index is not None:
                    self.can_interface.read_signal(member_index, signal_name)
                    
                    # Small delay between requests
                    time.sleep(0.1)
                    
    def _execute_custom_action(self, custom_action: Dict):
        """
        Execute a custom action.
        
        Args:
            custom_action: Custom action configuration
        """
        action_type = custom_action.get('type')
        
        if action_type == 'read_signal':
            # Read a specific signal
            signal_name = custom_action.get('signal')
            can_member = custom_action.get('can_member', 'PUMP')
            
            if signal_name:
                member_index = self._get_can_member_index(can_member)
                if member_index is not None:
                    self.can_interface.read_signal(member_index, signal_name)
                    
        elif action_type == 'write_signal':
            # Write a specific value to a signal
            signal_name = custom_action.get('signal')
            can_member = custom_action.get('can_member', 'PUMP')
            value = custom_action.get('value')
            
            if signal_name and value is not None:
                member_index = self._get_can_member_index(can_member)
                if member_index is not None:
                    self.can_interface.write_signal(member_index, signal_name, value)
                    
        elif action_type == 'sequence':
            # Execute a sequence of actions
            actions = custom_action.get('actions', [])
            for action in actions:
                self._execute_custom_action(action)
                
                # Delay between actions if specified
                delay = action.get('delay', 0.5)
                time.sleep(delay)


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description='Stiebel Eltron heat pump control')
    parser.add_argument('--config', dest='config_file', 
                        default='config.yaml',
                        help='Path to configuration file')
    args = parser.parse_args()
    
    # Initialize and start the application
    app = StiebelControl(args.config_file)
    if app.start():
        try:
            # Run until interrupted
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            app.stop()
    else:
        logger.error("Failed to start application")


if __name__ == '__main__':
    main()
