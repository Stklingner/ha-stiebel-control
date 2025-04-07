"""
ElsterTable module - contains the mapping of Stiebel Eltron signal codes.

This is a Python port of the original C++ implementation in ElsterTable.h.
Generated automatically by the convert_elster_table_improved.py script.
"""

import os
import yaml
import logging
from enum import Enum, auto
from pathlib import Path
from typing import List, Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)

class ElsterType(Enum):
    """Enumeration of Elster value types."""
    ET_NONE = auto()        # Unknown/unspecified type (read-only)
    ET_INTEGER = auto()
    ET_BOOLEAN = auto()
    ET_TEMPERATURE = auto()
    ET_DOUBLE_VALUE = auto()
    ET_TRIPLE_VALUE = auto()
    ET_HOUR = auto()
    ET_HOUR_SHORT = auto()
    ET_DATE = auto()
    ET_PERCENT = auto()
    ET_KELVIN = auto()
    ET_PRESSURE = auto()
    ET_MODE = auto()
    ET_PROGRAM_SWITCH = auto()
    ET_PROGRAM_TEXT = auto()


# Import enum values into global namespace for backward compatibility
ET_NONE = ElsterType.ET_NONE
ET_INTEGER = ElsterType.ET_INTEGER
ET_BOOLEAN = ElsterType.ET_BOOLEAN
ET_TEMPERATURE = ElsterType.ET_TEMPERATURE
ET_DOUBLE_VALUE = ElsterType.ET_DOUBLE_VALUE
ET_TRIPLE_VALUE = ElsterType.ET_TRIPLE_VALUE
ET_HOUR = ElsterType.ET_HOUR
ET_HOUR_SHORT = ElsterType.ET_HOUR_SHORT
ET_DATE = ElsterType.ET_DATE
ET_PERCENT = ElsterType.ET_PERCENT
ET_KELVIN = ElsterType.ET_KELVIN
ET_PRESSURE = ElsterType.ET_PRESSURE
ET_MODE = ElsterType.ET_MODE
ET_PROGRAM_SWITCH = ElsterType.ET_PROGRAM_SWITCH
ET_PROGRAM_TEXT = ElsterType.ET_PROGRAM_TEXT


class ElsterIndex:
    """Class representing an Elster signal index with metadata."""
    
    def __init__(self, name, english_name, index, value_type):
        """Initialize ElsterIndex.
        
        Args:
            name (str): Original German name of the signal
            english_name (str): English name of the signal
            index (int): Signal index
            value_type (ElsterType): Type of the signal value
        """
        self.name = name
        self.english_name = english_name
        self.index = index
        self.type = value_type


def load_elster_signals_from_yaml() -> List[ElsterIndex]:
    """
    Load Elster signal definitions from YAML file.
    
    Returns:
        list: List of ElsterIndex objects
    """
    # Define an emergency fallback in case loading fails
    fallback_signals = [
        ElsterIndex("INDEX_NOT_FOUND", "INDEX_NOT_FOUND", 0, ET_NONE),
    ]
    
    config_file = Path(__file__).parent.parent / 'config' / 'elster_signals.yaml'
    
    if not config_file.exists():
        logger.warning(f"Elster signals YAML file not found: {config_file}")
        return fallback_signals
    
    try:
        with open(config_file, 'r') as f:
            signals_data = yaml.safe_load(f)
        
        signals = []
        for signal_data in signals_data:
            # Convert string type to ElsterType enum
            type_string = signal_data['type']
            
            # Handle ElsterType.ET_XXX format
            if type_string.startswith('ElsterType.'):
                type_string = type_string[11:]  # Remove 'ElsterType.' prefix
            
            # Get ElsterType value by name
            if hasattr(ElsterType, type_string):
                value_type = getattr(ElsterType, type_string)
            else:
                # Default to ET_NONE if type not found
                logger.warning(f"Unknown ElsterType '{type_string}' for signal {signal_data['name']}, defaulting to ET_NONE")
                value_type = ElsterType.ET_NONE
            
            signal = ElsterIndex(
                signal_data['name'],
                signal_data['english_name'],
                signal_data['index'],
                value_type
            )
            signals.append(signal)
        
        logger.info(f"Loaded {len(signals)} Elster signals from YAML file")
        return signals
    except Exception as e:
        logger.error(f"Failed to load Elster signals from YAML: {e}")
        return fallback_signals


# Load signals from YAML file
ELSTER_TABLE = load_elster_signals_from_yaml()


# Create lookup dictionaries for fast index lookups
ELSTER_INDEX_BY_NAME = {signal.name: signal for signal in ELSTER_TABLE}
ELSTER_INDEX_BY_ENGLISH_NAME = {signal.english_name: signal for signal in ELSTER_TABLE}
ELSTER_INDEX_BY_INDEX = {signal.index: signal for signal in ELSTER_TABLE}


# BetriebsartList from original C++ code
BETRIEBSARTLIST = {
    0: "Notbetrieb",
    1: "Bereitschaft",
    2: "Programmbetrieb",
    3: "Tagbetrieb",
    4: "Absenkbetrieb",
    5: "Sommer(WW)",
    6: "Aus"
}

# ErrorList from original C++ code
ERRORLIST = {
    4: "DS",
    8: "BWT",
    12: "EVU",
    16: "WS",
    20: "MOT",
    24: "HD",
    28: "ND",
    30: "VD",
    32: "HG",
    34: "GG",
    36: "PD",
    38: "LMD",
    40: "TL",
    42: "VK",
    44: "HDW",
    48: "SWT",
    52: "AGF",
    56: "TK",
    58: "LP",
    60: "OSDK",
    62: "Geraetefehler",
    64: "pTKHDG",
    68: "Frostschutz",
    72: "Wartung"
}


def get_elster_index_by_name(name):
    """Get ElsterIndex by German name.
    
    Args:
        name (str): German name of the signal
        
    Returns:
        ElsterIndex: Corresponding ElsterIndex or UNKNOWN if not found
    """
    return ELSTER_INDEX_BY_NAME.get(name, ELSTER_TABLE[0])


def get_elster_index_by_english_name(english_name):
    """Get ElsterIndex by English name.
    
    Args:
        english_name (str): English name of the signal
        
    Returns:
        ElsterIndex: Corresponding ElsterIndex or UNKNOWN if not found
    """
    return ELSTER_INDEX_BY_ENGLISH_NAME.get(english_name, ELSTER_TABLE[0])


def get_elster_index_by_index(index):
    """Get ElsterIndex by index value.
    
    Args:
        index (int): Index value of the signal
        
    Returns:
        ElsterIndex: Corresponding ElsterIndex or UNKNOWN if not found
    """
    return ELSTER_INDEX_BY_INDEX.get(index, ELSTER_TABLE[0])


def translate_value(value, value_type):
    """Translate a raw value according to its type.
    
    Args:
        value (int): Raw value from CAN message
        value_type (ElsterType): Type of the value
        
    Returns:
        int, float, bool, or str: Properly typed and scaled value
    """
    if value_type == ElsterType.ET_NONE:
        return value  # Return raw value without conversion for ET_NONE type
    elif value_type == ElsterType.ET_BOOLEAN:
        return bool(value)
    elif value_type == ElsterType.ET_TEMPERATURE:
        # Handle temperature as signed value (convert to signed 16-bit)
        if value > 32767:  # If high bit is set, it's negative
            signed_value = value - 65536
            return signed_value / 10.0
        return value / 10.0  # Temperature values are scaled by 10
    elif value_type == ElsterType.ET_DOUBLE_VALUE or value_type == ElsterType.ET_TRIPLE_VALUE:
        # These may also need signed handling
        if value > 32767:  # If high bit is set, it's negative
            signed_value = value - 65536
            return signed_value / 10.0
        return value / 10.0  # Double/triple values are scaled by 10
    elif value_type == ElsterType.ET_PERCENT:
        return value / 10.0  # Percent values are scaled by 10
    elif value_type == ElsterType.ET_PROGRAM_SWITCH:
        # Use the BetriebsartList if available
        if 'BETRIEBSARTLIST' in globals():
            return BETRIEBSARTLIST.get(value, "Unknown")
        else:
            program_states = {
                0: "Emergency",
                1: "Standby",
                2: "Automatic",
                3: "Day mode",
                4: "Night mode",
                5: "DHW",
                6: "Unknown"
            }
            return program_states.get(value, "Unknown")
    elif value_type == ElsterType.ET_HOUR or value_type == ElsterType.ET_HOUR_SHORT:
        return value / 3600  # Hours are in seconds
    elif value_type == ElsterType.ET_DATE:
        # Format as YYYY-MM-DD (assuming value is in format YYYYMMDD)
        year = value // 10000
        month = (value // 100) % 100
        day = value % 100
        return f"{year:04d}-{month:02d}-{day:02d}"
    else:
        return value  # No translation for other types


def translate_string_to_value(string_value, value_type):
    """Translate a string value to the raw integer value according to type.
    
    Args:
        string_value (str): String representation of value
        value_type (ElsterType): Type of the value
        
    Returns:
        int: Raw value for CAN message
        
    Raises:
        ValueError: If the string value cannot be converted to the specified type
    """
    if value_type == ElsterType.ET_NONE:
        raise ValueError("Cannot write to signals with ET_NONE type")
    elif value_type == ElsterType.ET_BOOLEAN:
        return 1 if string_value.lower() in ["true", "1", "on", "yes"] else 0
    elif value_type == ElsterType.ET_TEMPERATURE:
        # Multiply by 10 to store as fixed-point
        # If negative, will be properly encoded as 16-bit signed
        float_val = float(string_value) * 10
        # Convert to 16-bit signed integer representation if needed
        if float_val < 0:
            return int(float_val) & 0xFFFF  # Convert to 16-bit unsigned representation of signed value
        return int(float_val)
    elif value_type == ElsterType.ET_DOUBLE_VALUE or value_type == ElsterType.ET_TRIPLE_VALUE:
        # Multiply by 10 to store as fixed-point
        float_val = float(string_value) * 10
        # Convert to 16-bit signed integer representation if needed
        if float_val < 0:
            return int(float_val) & 0xFFFF  # Convert to 16-bit unsigned representation of signed value
        return int(float_val)
    elif value_type == ElsterType.ET_PERCENT:
        # Percent values are scaled by 10
        float_val = float(string_value) * 10
        return int(float_val)
    elif value_type == ElsterType.ET_PROGRAM_SWITCH:
        # Use the BetriebsartList if available
        if 'BETRIEBSARTLIST' in globals():
            # Reverse lookup in BETRIEBSARTLIST
            for code, desc in BETRIEBSARTLIST.items():
                if desc == string_value:
                    return code
            return 0  # Default to first value if not found
        else:
            program_states = {
                "Emergency": 0,
                "Standby": 1,
                "Automatic": 2, 
                "Day mode": 3,
                "Night mode": 4,
                "DHW": 5,
                "Unknown": 6
            }
            return program_states.get(string_value, 0)
    elif value_type == ElsterType.ET_HOUR or value_type == ElsterType.ET_HOUR_SHORT:
        return int(float(string_value) * 3600)  # Hours to seconds
    elif value_type == ElsterType.ET_DATE:
        # Parse YYYY-MM-DD and convert to YYYYMMDD integer
        parts = string_value.split('-')
        if len(parts) == 3:
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])
            return year * 10000 + month * 100 + day
        else:
            return 0
    else:
        return int(string_value)  # Simple int conversion for other types
