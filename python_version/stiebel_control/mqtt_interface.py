"""
MQTT Interface module for communication with Home Assistant.

This module handles the MQTT communication with Home Assistant, 
publishing sensor values and subscribing to command topics.
"""

import json
import logging
import time
from typing import Dict, Any, Callable, Optional

import paho.mqtt.client as mqtt

# Configure logger
logger = logging.getLogger(__name__)


class MqttInterface:
    """
    Interface for MQTT communication with Home Assistant.
    
    This class handles the MQTT communication, including automatic discovery 
    for Home Assistant, publishing sensor values, and subscribing to command topics.
    """
    
    def __init__(self, host: str, port: int = 1883, username: str = None, password: str = None,
                 client_id: str = "stiebel_control", 
                 discovery_prefix: str = "homeassistant",
                 base_topic: str = "stiebel_control",
                 command_callback: Optional[Callable[[str, Any], None]] = None):
        """
        Initialize the MQTT interface.
        
        Args:
            host: MQTT broker hostname or IP
            port: MQTT broker port
            username: MQTT username (optional)
            password: MQTT password (optional)
            client_id: MQTT client ID
            discovery_prefix: Home Assistant discovery prefix
            base_topic: Base topic for this device
            command_callback: Callback function for commands received via MQTT
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.discovery_prefix = discovery_prefix
        self.base_topic = base_topic
        self.command_callback = command_callback
        
        # Initialize MQTT client
        self.client = mqtt.Client(client_id=client_id)
        if username and password:
            self.client.username_pw_set(username, password)
            
        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        # Flag to track connection state
        self.connected = False
        
        # Dictionary to track registered entities
        self.entities = {}
        
    def connect(self) -> bool:
        """
        Connect to the MQTT broker.
        
        Returns:
            bool: True if connected successfully, False otherwise
        """
        try:
            self.client.connect(self.host, self.port)
            self.client.loop_start()
            
            # Wait for connection to establish
            for _ in range(5):
                if self.connected:
                    return True
                time.sleep(1)
                
            logger.error(f"Failed to connect to MQTT broker at {self.host}:{self.port}")
            return False
            
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from the MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False
        logger.info("Disconnected from MQTT broker")
        
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker."""
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {self.host}:{self.port}")
            self.connected = True
            
            # Subscribe to command topics
            command_topic = f"{self.base_topic}/+/command"
            client.subscribe(command_topic)
            logger.debug(f"Subscribed to {command_topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
            
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker."""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker, return code: {rc}")
        else:
            logger.info("Disconnected from MQTT broker")
            
    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received from the broker."""
        topic = msg.topic
        try:
            payload = msg.payload.decode('utf-8')
            logger.debug(f"Received message on topic {topic}: {payload}")
            
            # Check if this is a command topic
            if topic.endswith('/command'):
                entity_id = topic.split('/')[-2]
                if self.command_callback:
                    self.command_callback(entity_id, payload)
                    
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            
    def register_sensor(self, entity_id: str, name: str, device_class: str = None,
                      state_class: str = None, unit_of_measurement: str = None,
                      icon: str = None) -> bool:
        """
        Register a sensor with Home Assistant using MQTT discovery.
        
        Args:
            entity_id: Unique ID for the sensor
            name: Display name for the sensor
            device_class: Home Assistant device class (e.g., 'temperature')
            state_class: Home Assistant state class (e.g., 'measurement')
            unit_of_measurement: Unit of measurement (e.g., '°C')
            icon: Icon to use (e.g., 'mdi:thermometer')
            
        Returns:
            bool: True if registered successfully, False otherwise
        """
        if not self.connected:
            logger.error("Cannot register sensor: not connected to MQTT broker")
            return False
            
        try:
            # Create the state topic where sensor values will be published
            state_topic = f"{self.base_topic}/{entity_id}/state"
            
            # Create the discovery payload
            config = {
                "name": name,
                "unique_id": f"{self.client_id}_{entity_id}",
                "state_topic": state_topic,
                "device": {
                    "identifiers": [self.client_id],
                    "name": "Stiebel Eltron Heat Pump",
                    "model": "CAN Interface",
                    "manufacturer": "Stiebel Eltron"
                }
            }
            
            # Add optional fields if provided
            if device_class:
                config["device_class"] = device_class
            if state_class:
                config["state_class"] = state_class
            if unit_of_measurement:
                config["unit_of_measurement"] = unit_of_measurement
            if icon:
                config["icon"] = icon
                
            # Create the discovery topic
            discovery_topic = f"{self.discovery_prefix}/sensor/{self.client_id}/{entity_id}/config"
            
            # Publish the discovery message
            self.client.publish(discovery_topic, json.dumps(config), qos=1, retain=True)
            logger.debug(f"Registered sensor {entity_id} with Home Assistant")
            
            # Store the entity info for later use
            self.entities[entity_id] = {
                "type": "sensor",
                "state_topic": state_topic,
                "config": config
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error registering sensor: {e}")
            return False
            
    def register_select(self, entity_id: str, name: str, options: list,
                       icon: str = None) -> bool:
        """
        Register a select entity with Home Assistant using MQTT discovery.
        
        Args:
            entity_id: Unique ID for the select entity
            name: Display name for the select
            options: List of options for the select
            icon: Icon to use (e.g., 'mdi:menu')
            
        Returns:
            bool: True if registered successfully, False otherwise
        """
        if not self.connected:
            logger.error("Cannot register select: not connected to MQTT broker")
            return False
            
        try:
            # Create the topics
            state_topic = f"{self.base_topic}/{entity_id}/state"
            command_topic = f"{self.base_topic}/{entity_id}/command"
            
            # Create the discovery payload
            config = {
                "name": name,
                "unique_id": f"{self.client_id}_{entity_id}",
                "state_topic": state_topic,
                "command_topic": command_topic,
                "options": options,
                "device": {
                    "identifiers": [self.client_id],
                    "name": "Stiebel Eltron Heat Pump",
                    "model": "CAN Interface",
                    "manufacturer": "Stiebel Eltron"
                }
            }
            
            # Add optional fields if provided
            if icon:
                config["icon"] = icon
                
            # Create the discovery topic
            discovery_topic = f"{self.discovery_prefix}/select/{self.client_id}/{entity_id}/config"
            
            # Publish the discovery message
            self.client.publish(discovery_topic, json.dumps(config), qos=1, retain=True)
            logger.debug(f"Registered select {entity_id} with Home Assistant")
            
            # Store the entity info for later use
            self.entities[entity_id] = {
                "type": "select",
                "state_topic": state_topic,
                "command_topic": command_topic,
                "config": config
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error registering select: {e}")
            return False
            
    def register_button(self, entity_id: str, name: str, icon: str = None) -> bool:
        """
        Register a button entity with Home Assistant using MQTT discovery.
        
        Args:
            entity_id: Unique ID for the button
            name: Display name for the button
            icon: Icon to use (e.g., 'mdi:refresh')
            
        Returns:
            bool: True if registered successfully, False otherwise
        """
        if not self.connected:
            logger.error("Cannot register button: not connected to MQTT broker")
            return False
            
        try:
            # Create the command topic
            command_topic = f"{self.base_topic}/{entity_id}/command"
            
            # Create the discovery payload
            config = {
                "name": name,
                "unique_id": f"{self.client_id}_{entity_id}",
                "command_topic": command_topic,
                "device": {
                    "identifiers": [self.client_id],
                    "name": "Stiebel Eltron Heat Pump",
                    "model": "CAN Interface",
                    "manufacturer": "Stiebel Eltron"
                }
            }
            
            # Add optional fields if provided
            if icon:
                config["icon"] = icon
                
            # Create the discovery topic
            discovery_topic = f"{self.discovery_prefix}/button/{self.client_id}/{entity_id}/config"
            
            # Publish the discovery message
            self.client.publish(discovery_topic, json.dumps(config), qos=1, retain=True)
            logger.debug(f"Registered button {entity_id} with Home Assistant")
            
            # Store the entity info for later use
            self.entities[entity_id] = {
                "type": "button",
                "command_topic": command_topic,
                "config": config
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error registering button: {e}")
            return False
            
    def publish_state(self, entity_id: str, state: Any) -> bool:
        """
        Publish a state update for an entity.
        
        Args:
            entity_id: ID of the entity to update
            state: New state value
            
        Returns:
            bool: True if published successfully, False otherwise
        """
        if not self.connected:
            logger.error("Cannot publish state: not connected to MQTT broker")
            return False
            
        if entity_id not in self.entities:
            logger.warning(f"Entity {entity_id} not registered")
            return False
            
        try:
            # Get the state topic for this entity
            entity_info = self.entities[entity_id]
            if "state_topic" not in entity_info:
                logger.warning(f"Entity {entity_id} has no state topic")
                return False
                
            state_topic = entity_info["state_topic"]
            
            # Convert state to string if necessary
            if not isinstance(state, str):
                state = str(state)
                
            # Publish the state
            self.client.publish(state_topic, state, qos=1)
            logger.debug(f"Published state for {entity_id}: {state}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error publishing state: {e}")
            return False
