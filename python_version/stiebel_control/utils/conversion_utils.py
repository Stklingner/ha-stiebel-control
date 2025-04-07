"""
Value conversion utilities for the Stiebel Control package.
"""
from typing import Any, Dict, Optional, Union
import logging

logger = logging.getLogger(__name__)

def apply_transformation(value: Any, transform_config: Dict[str, Any]) -> Any:
    """
    Apply a transformation to a value.
    
    Args:
        value: Value to transform
        transform_config: Transformation configuration with 'type' and other parameters
        
    Returns:
        Transformed value
    """
    if not transform_config:
        return value
        
    transform_type = transform_config.get('type', '').lower()
    
    if transform_type == 'scale':
        # Apply scaling transformation
        factor = transform_config.get('factor', 1.0)
        offset = transform_config.get('offset', 0.0)
        return (value * factor) + offset
    elif transform_type == 'map':
        # Apply mapping transformation
        mapping = transform_config.get('mapping', {})
        # Convert value to string for mapping lookup
        str_value = str(value)
        if str_value in mapping:
            return mapping[str_value]
        else:
            # Return the original value if no mapping found
            logger.warning(f"No mapping found for value '{value}', using original value")
            return value
    elif transform_type == 'boolean':
        # Apply boolean transformation
        true_value = transform_config.get('true_value', 1)
        return value == true_value
    else:
        logger.warning(f"Unknown transformation type: {transform_type}, using original value")
        return value
        
def format_value_for_display(value: Any, device_class: Optional[str] = None, 
                            unit_of_measurement: Optional[str] = None) -> str:
    """
    Format a value for display in Home Assistant.
    
    Args:
        value: Value to format
        device_class: Home Assistant device class
        unit_of_measurement: Unit of measurement
        
    Returns:
        Formatted value as string
    """
    # Return None as an empty string
    if value is None:
        return ""
        
    # Format based on device class
    if device_class == "temperature":
        if isinstance(value, (int, float)):
            return f"{value:.1f}"
    elif device_class == "energy":
        if isinstance(value, (int, float)):
            return f"{value:.2f}"
            
    # Default formatting for numeric values
    if isinstance(value, float):
        return f"{value:.2f}"
    
    # Return other values as string
    return str(value)
