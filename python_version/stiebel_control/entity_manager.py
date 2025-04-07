"""
Entity management for the Stiebel Control package.
"""
import logging
from typing import Dict, Any, Optional, List, Set, Tuple, Union
from stiebel_control.mqtt_interface import MqttInterface
from stiebel_control.elster_table import (
    get_elster_index_by_english_name, 
    ElsterIndex, 
    ElsterType,
    BETRIEBSARTLIST
)

logger = logging.getLogger(__name__)

class EntityManager:
    """
    Manages Home Assistant entities and their registration.
    """
    
    def __init__(self, mqtt_interface: MqttInterface, config_manager):
        """
        Initialize the entity manager.
        
        Args:
            mqtt_interface: MQTT interface for Home Assistant communication
            config_manager: Configuration manager
        """
        self.mqtt_interface = mqtt_interface
        self.config_manager = config_manager
        self.entity_config = config_manager.get_entity_config()
        self.dynamic_registration_enabled = config_manager.is_dynamic_registration_enabled()
        
        # Track registered entities to avoid duplicates
        self.registered_entities = set()
        
        # Entity mapping from signal to entity ID
        self.entity_map = {}  # Format: {(signal_name, can_id): entity_id}
        
        logger.info(f"Entity manager initialized with dynamic registration {'enabled' if self.dynamic_registration_enabled else 'disabled'}")
        
    def build_entity_mapping(self, can_interface) -> None:
        """
        Build mapping between CAN signals and Home Assistant entities.
        
        Args:
            can_interface: CAN interface for resolving CAN IDs
        """
        logger.info("Building entity mapping from configuration")
        
        if not self.entity_config:
            logger.warning("No entity configuration found")
            return
            
        # Process each entity in the configuration
        for entity_id, entity_def in self.entity_config.items():
            signal_name = entity_def.get('signal')
            can_member = entity_def.get('can_member')
            can_member_ids = entity_def.get('can_member_ids', [])
            
            if not signal_name:
                logger.warning(f"Missing signal name for entity {entity_id}")
                continue
                
            # Process entities that define a single CAN member
            if can_member and not can_member_ids:
                can_id = can_interface.get_can_id_by_name(can_member)
                if can_id is not None:
                    self.entity_map[(signal_name, can_id)] = entity_id
                    logger.debug(f"Mapped signal {signal_name} from {can_member} (ID: 0x{can_id:X}) to entity {entity_id}")
                else:
                    logger.warning(f"Unknown CAN member '{can_member}' for entity {entity_id}")
                    
            # Process entities that define multiple CAN members
            elif can_member_ids:
                for member_id in can_member_ids:
                    self.entity_map[(signal_name, member_id)] = entity_id
                    logger.debug(f"Mapped signal {signal_name} from CAN ID 0x{member_id:X} to entity {entity_id}")
            
            # Register the entity with Home Assistant
            self._register_entity_from_config(entity_id, entity_def)
            
        logger.info(f"Built entity mapping with {len(self.entity_map)} signal-to-entity mappings")
        
    def _register_entity_from_config(self, entity_id: str, entity_def: Dict[str, Any]) -> None:
        """
        Register an entity with Home Assistant based on configuration.
        
        Args:
            entity_id: Unique entity ID
            entity_def: Entity definition from configuration
        """
        entity_type = entity_def.get('type', 'sensor')
        name = entity_def.get('name', entity_id)
        
        if entity_type == 'sensor':
            # Register a sensor entity
            self.mqtt_interface.register_sensor(
                entity_id=entity_id,
                name=name,
                device_class=entity_def.get('device_class'),
                state_class=entity_def.get('state_class'),
                unit_of_measurement=entity_def.get('unit_of_measurement'),
                icon=entity_def.get('icon')
            )
        elif entity_type == 'binary_sensor':
            # Register a binary sensor entity
            self.mqtt_interface.register_binary_sensor(
                entity_id=entity_id,
                name=name,
                device_class=entity_def.get('device_class'),
                icon=entity_def.get('icon')
            )
        elif entity_type == 'select':
            # Register a select entity
            options = entity_def.get('options', [])
            self.mqtt_interface.register_select(
                entity_id=entity_id,
                name=name,
                options=options,
                icon=entity_def.get('icon')
            )
        else:
            logger.warning(f"Unsupported entity type '{entity_type}' for entity {entity_id}")
            return
            
        # Add to registered entities
        self.registered_entities.add(entity_id)
        logger.info(f"Registered {entity_type} entity {entity_id}")
        
    def get_entity_by_signal(self, signal_name: str, can_id: int) -> Optional[str]:
        """
        Get entity ID for a given signal and CAN ID.
        
        Args:
            signal_name: Name of the signal
            can_id: CAN ID of the member that sent the message
            
        Returns:
            Entity ID, or None if no mapping found
        """
        return self.entity_map.get((signal_name, can_id))
        
    def dynamically_register_entity(self, signal_name: str, value: Any, can_id: int) -> Optional[str]:
        """
        Dynamically register an entity with Home Assistant based on signal characteristics.
        
        Args:
            signal_name: Name of the signal
            value: Current value of the signal
            can_id: CAN ID of the member that sent the message
            
        Returns:
            str: The newly created entity ID, or None if registration failed
        """
        if not self.dynamic_registration_enabled:
            return None
            
        # Get signal information
        ei = get_elster_index_by_english_name(signal_name)
        if ei.name == "UNKNOWN":
            logger.warning(f"Cannot register unknown signal: {signal_name}")
            return None
            
        # Get CAN member name from ID
        can_member_name = self._get_can_member_name_from_id(can_id)
        if not can_member_name:
            logger.warning(f"Cannot register signal from unknown CAN ID: 0x{can_id:X}")
            return None
            
        # Create a unique entity ID based on CAN member and signal
        # Format: can_member_signal_name (lowercase, underscores)
        entity_id = f"{can_member_name.lower()}_{signal_name.lower()}"
        entity_id = entity_id.replace(' ', '_')
        
        # If entity already exists, don't register again
        if entity_id in self.registered_entities:
            return entity_id
            
        # Create a friendly name with proper capitalization and spaces
        # Format: Can Member Signal Name (Title Case, spaces)
        friendly_name = f"{can_member_name.title()} {signal_name.title()}"
        friendly_name = friendly_name.replace('_', ' ')
        
        # Determine entity type and attributes based on signal type
        entity_type = "sensor"  # Default entity type
        device_class = None
        state_class = "measurement"
        unit_of_measurement = None
        icon = None
        
        # Match signal type to appropriate entity configuration
        if ei.type == ElsterType.ET_TEMPERATURE:
            device_class = "temperature"
            unit_of_measurement = "°C"
            icon = "mdi:thermometer-lines"
        elif ei.type == ElsterType.ET_BOOLEAN:
            device_class = "binary_sensor"
            icon = "mdi:toggle-switch"
        elif ei.type == ElsterType.ET_PERCENT:
            unit_of_measurement = "%"
            icon = "mdi:percent"
        elif ei.type == ElsterType.ET_HOUR or ei.type == ElsterType.ET_HOUR_SHORT:
            device_class = "duration"
            unit_of_measurement = "h"
            icon = "mdi:timer"
        elif ei.type == ElsterType.ET_PROGRAM_SWITCH:
            # This should be a select entity, not a sensor
            entity_type = "select"
            icon = "mdi:tune-vertical"
        elif ei.type == ElsterType.ET_DATE:
            device_class = "date"
            icon = "mdi:calendar"
        elif ei.type == ElsterType.ET_DOUBLE_VALUE or ei.type == ElsterType.ET_TRIPLE_VALUE:
            # Likely energy value, but could be other types
            if "ENERGY" in signal_name or "KWH" in signal_name:
                device_class = "energy"
                unit_of_measurement = "kWh"
                icon = "mdi:lightning-bolt"
            elif "POWER" in signal_name:
                device_class = "power"
                unit_of_measurement = "W"
                icon = "mdi:flash"
            else:
                # Generic numeric value
                unit_of_measurement = ""
                icon = "mdi:numeric"
                
        # Register the entity with Home Assistant
        logger.info(f"Dynamically registering {entity_type} for signal {signal_name} from {can_member_name}")
        
        if entity_type == "sensor":
            registered = self.mqtt_interface.register_sensor(
                entity_id=entity_id,
                name=friendly_name,
                device_class=device_class,
                state_class=state_class,
                unit_of_measurement=unit_of_measurement,
                icon=icon
            )
        elif entity_type == "select" and isinstance(value, str):
            # For selects, we need to determine the options
            # For program switches, we use betriebsartlist values
            options = list(BETRIEBSARTLIST.values()) if hasattr(BETRIEBSARTLIST, 'values') else []
            
            registered = self.mqtt_interface.register_select(
                entity_id=entity_id,
                name=friendly_name,
                options=options,
                icon=icon
            )
        else:
            # Fallback to sensor for unsupported types
            registered = self.mqtt_interface.register_sensor(
                entity_id=entity_id,
                name=friendly_name,
                icon="mdi:help-circle"
            )
            
        if registered:
            logger.info(f"Successfully registered dynamic entity {entity_id}")
            # Add to registered entities
            self.registered_entities.add(entity_id)
            # Update entity map
            self.entity_map[(signal_name, can_id)] = entity_id
            return entity_id
        else:
            logger.warning(f"Failed to register dynamic entity for {signal_name}")
            return None
            
    def _get_can_member_name_from_id(self, can_id: int) -> Optional[str]:
        """
        Get the name of a CAN member from its ID.
        
        Args:
            can_id: CAN ID to look up
            
        Returns:
            Name of the CAN member, or None if not found
        """
        # Hardcoded mapping of CAN IDs to member names
        # This should ideally come from the CAN interface
        can_id_to_name = {
            0x180: "PUMP",
            0x480: "MANAGER",
            0x301: "FE7X", 
            0x302: "FEK",
            0x500: "HEATING",  # Heating Module (0x500)
            0x602: "FE7",
            0x680: "ESPCLIENT"
        }
        
        return can_id_to_name.get(can_id)
