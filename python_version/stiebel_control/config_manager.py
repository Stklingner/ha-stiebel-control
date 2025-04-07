"""
Configuration management for the Stiebel Control package.
"""
import os
import yaml
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    Manages loading and validation of configuration files.
    """
    
    def __init__(self, service_config_path: str):
        """
        Initialize the configuration manager.
        
        Args:
            service_config_path: Path to the service configuration file
        """
        self.service_config_path = service_config_path
        self.service_config = self._load_yaml(service_config_path)
        
        # Load entity configuration
        entity_config_path = self.service_config.get('entity_config')
        if not os.path.isabs(entity_config_path):
            # Convert relative path to absolute path
            base_dir = os.path.dirname(os.path.abspath(service_config_path))
            entity_config_path = os.path.join(base_dir, entity_config_path)
            
        self.entity_config = self._load_yaml(entity_config_path)
        
        logger.info(f"Loaded configuration from {service_config_path} and {entity_config_path}")
        
    def _load_yaml(self, file_path: str) -> Dict[str, Any]:
        """
        Load a YAML file.
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            Parsed YAML content as dictionary
        """
        try:
            with open(file_path, 'r') as file:
                return yaml.safe_load(file) or {}
        except Exception as e:
            logger.error(f"Error loading configuration from {file_path}: {e}")
            return {}
            
    def get_logging_config(self) -> Dict[str, Any]:
        """
        Get logging configuration.
        
        Returns:
            Logging configuration
        """
        return self.service_config.get('logging', {'level': 'INFO'})
        
    def get_can_config(self) -> Dict[str, Any]:
        """
        Get CAN interface configuration.
        
        Returns:
            CAN configuration
        """
        return self.service_config.get('can', {})
        
    def get_mqtt_config(self) -> Dict[str, Any]:
        """
        Get MQTT configuration.
        
        Returns:
            MQTT configuration
        """
        return self.service_config.get('mqtt', {})
        
    def get_update_interval(self) -> int:
        """
        Get update interval in seconds.
        
        Returns:
            Update interval
        """
        return int(self.service_config.get('update_interval', 60))
        
    def get_entity_config(self) -> Dict[str, Dict[str, Any]]:
        """
        Get entity configuration.
        
        Returns:
            Entity configuration
        """
        return self.entity_config
        
    def is_dynamic_registration_enabled(self) -> bool:
        """
        Check if dynamic entity registration is enabled.
        
        Returns:
            True if dynamic registration is enabled, False otherwise
        """
        return self.service_config.get('dynamic_entity_registration', False)
