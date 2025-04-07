"""
Signal processing for the Stiebel Control package.
"""
import logging
from typing import Dict, Any, Optional, Callable, Union
from stiebel_control.utils.conversion_utils import apply_transformation
from stiebel_control.entity_manager import EntityManager

logger = logging.getLogger(__name__)

class SignalProcessor:
    """
    Processes signals from the CAN bus and updates Home Assistant entities.
    """
    
    def __init__(self, entity_manager: EntityManager, mqtt_interface, 
                 can_interface, config_manager):
        """
        Initialize the signal processor.
        
        Args:
            entity_manager: Entity manager for entity registration and lookup
            mqtt_interface: MQTT interface for publishing updates
            can_interface: CAN interface for accessing signal values
            config_manager: Configuration manager
        """
        self.entity_manager = entity_manager
        self.mqtt_interface = mqtt_interface
        self.can_interface = can_interface
        self.config_manager = config_manager
        self.entity_config = config_manager.get_entity_config()
        
        # Keep track of commands that are being processed
        self.pending_commands = {}
        
        logger.info("Signal processor initialized")
        
    def process_signal(self, signal_name: str, value: Any, can_id: int) -> None:
        """
        Process a signal update from the CAN bus.
        
        Args:
            signal_name: Name of the signal
            value: Updated signal value
            can_id: CAN ID of the member that sent the message
        """
        # First, try to find an existing entity for this signal
        entity_id = self.entity_manager.get_entity_by_signal(signal_name, can_id)
        
        if not entity_id:
            # If no existing entity found and dynamic registration is enabled,
            # try to create one dynamically
            entity_id = self.entity_manager.dynamically_register_entity(signal_name, value, can_id)
            
            if not entity_id:
                # No existing entity and dynamic registration failed or disabled
                logger.debug(f"No entity found for signal {signal_name} from CAN ID 0x{can_id:X}")
                return
                
        # Skip if this is a pending command being processed
        if entity_id in self.pending_commands:
            command_value = self.pending_commands[entity_id]
            if str(value) == str(command_value):
                logger.debug(f"Ignoring echo of command for entity {entity_id}: {value}")
                del self.pending_commands[entity_id]
                return
                
        # Get entity configuration
        entity_def = self.entity_config.get(entity_id, {})
        
        # Apply any transformations to the value
        transform_config = entity_def.get('transform', {})
        if transform_config:
            value = apply_transformation(value, transform_config)
            
        # Publish the updated value to MQTT
        self.mqtt_interface.publish_state(entity_id, value)
        logger.debug(f"Published state for entity {entity_id}: {value}")
        
    def handle_command(self, entity_id: str, payload: str) -> None:
        """
        Handle a command received from Home Assistant.
        
        Args:
            entity_id: Entity ID that received the command
            payload: Command payload
        """
        if not entity_id or not payload:
            logger.warning(f"Invalid command: entity_id={entity_id}, payload={payload}")
            return
            
        logger.info(f"Received command for entity {entity_id}: {payload}")
        
        # Find the entity in the configuration
        entity_def = self.entity_config.get(entity_id)
        if not entity_def:
            logger.warning(f"Cannot process command: no configuration for entity {entity_id}")
            return
            
        signal_name = entity_def.get('signal')
        can_member = entity_def.get('can_member')
        can_member_ids = entity_def.get('can_member_ids', [])
        
        if not signal_name:
            logger.warning(f"Cannot process command: no signal name for entity {entity_id}")
            return
            
        # Determine CAN ID for sending the command
        can_id = None
        if can_member:
            can_id = self.can_interface.get_can_id_by_name(can_member)
        elif can_member_ids and len(can_member_ids) > 0:
            # Use the first CAN member ID in the list
            can_id = can_member_ids[0]
            
        if can_id is None:
            logger.warning(f"Cannot process command: no valid CAN ID for entity {entity_id}")
            return
            
        # Apply inverse transformations if needed
        transform_config = entity_def.get('transform', {})
        if transform_config:
            # This is a simplified approach - a more complete implementation would
            # handle different types of transformations and their inverses
            if transform_config.get('type') == 'scale':
                factor = transform_config.get('factor', 1.0)
                offset = transform_config.get('offset', 0.0)
                if factor != 0:
                    # Apply inverse of scaling: (value - offset) / factor
                    try:
                        value = (float(payload) - offset) / factor
                    except ValueError:
                        logger.warning(f"Cannot convert payload to float: {payload}")
                        return
            elif transform_config.get('type') == 'map':
                mapping = transform_config.get('mapping', {})
                # Invert the mapping to go from display value to raw value
                inverse_mapping = {v: k for k, v in mapping.items()}
                if payload in inverse_mapping:
                    value = inverse_mapping[payload]
                else:
                    logger.warning(f"No inverse mapping for value: {payload}")
                    return
            else:
                # For other transformations, use the raw payload
                value = payload
        else:
            # No transformation, use the raw payload
            value = payload
            
        # Record that we're processing this command to avoid echo
        self.pending_commands[entity_id] = value
        
        # Send the command to the CAN bus
        self.can_interface.set_value(can_id, signal_name, value)
        logger.info(f"Sent command to CAN bus: signal={signal_name}, value={value}, can_id=0x{can_id:X}")
