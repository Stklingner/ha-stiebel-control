#!/usr/bin/env python3
"""
Improved Conversion tool to convert ElsterTable.h (C++ format) to Python format.

This script extracts the signal definitions from the ElsterTable.h file
and generates a Python-compatible version for use in the stiebel_control package.
"""

import os
import re
import argparse
from pathlib import Path
from typing import List, Dict, Tuple


def parse_elster_type_enum(content: str) -> Dict[str, str]:
    """
    Parse the ElsterType enum from the C++ header file.
    
    Args:
        content: Content of the ElsterTable.h file
        
    Returns:
        Dict mapping C++ enum values to Python enum values
    """
    # Define the regex pattern for the ElsterType enum
    enum_pattern = r'typedef\s+enum\s*\{(.*?)\}\s*ElsterType;'
    enum_match = re.search(enum_pattern, content, re.DOTALL)
    
    if not enum_match:
        print("WARNING: Could not find ElsterType enum definition in header file!")
        return {}
    
    enum_content = enum_match.group(1)
    
    # Extract individual enum values with their assigned values if present
    cpp_to_py = {}
    
    # Create a mapping from C++ type to Python type
    type_mapping = {
        'et_default': 'ET_INTEGER',
        'et_dec_val': 'ET_TEMPERATURE',  # Decimal values are usually temperatures
        'et_cent_val': 'ET_PERCENT',     # Cent values are usually percentages
        'et_mil_val': 'ET_TRIPLE_VALUE', # Thousandths precision
        'et_byte': 'ET_INTEGER',
        'et_bool': 'ET_BOOLEAN',
        'et_little_bool': 'ET_BOOLEAN',
        'et_double_val': 'ET_DOUBLE_VALUE',
        'et_triple_val': 'ET_TRIPLE_VALUE',
        'et_little_endian': 'ET_INTEGER',
        'et_betriebsart': 'ET_PROGRAM_SWITCH',
        'et_zeit': 'ET_HOUR',
        'et_datum': 'ET_DATE',
        'et_time_domain': 'ET_INTEGER',
        'et_dev_nr': 'ET_INTEGER',
        'et_err_nr': 'ET_INTEGER',
        'et_dev_id': 'ET_INTEGER'
    }
    
    for cpp_type, py_type in type_mapping.items():
        cpp_to_py[cpp_type] = py_type
    
    return cpp_to_py


def parse_elster_table(content: str, type_map: Dict[str, str]) -> List[Dict]:
    """
    Parse the ElsterTable array from the C++ header file.
    
    Args:
        content: Content of the ElsterTable.h file
        type_map: Mapping of C++ type names to Python type names
        
    Returns:
        List of dictionaries representing ElsterIndex entries
    """
    # Find the ElsterTable definition
    table_pattern = r'static\s+const\s+ElsterIndex\s+ElsterTable\[\]\s*=\s*\{(.*?)\};'
    table_match = re.search(table_pattern, content, re.DOTALL)
    
    if not table_match:
        print("WARNING: Could not find ElsterTable definition in header file!")
        return []
    
    table_content = table_match.group(1)
    
    # Split the content into individual entries
    entries = []
    # Regular expression to match each table entry
    entry_pattern = r'\{"([^"]+)"\s*,\s*(0x[0-9a-fA-F]+|\d+)\s*,\s*([a-zA-Z0-9_]+)\s*,\s*"([^"]*)"\}'
    
    for match in re.finditer(entry_pattern, table_content):
        name = match.group(1)
        index_str = match.group(2)
        cpp_type = match.group(3)
        english_name = match.group(4) or name  # Use name if English name is empty
        
        # Convert hex format to int
        if index_str.startswith('0x'):
            index_val = int(index_str, 16)
        else:
            index_val = int(index_str)
            
        # Map the C++ type to Python type
        py_type = type_map.get(cpp_type, "ElsterType.ET_INTEGER")  # Default to INTEGER if type not found
        
        entries.append({
            "name": name,
            "english_name": english_name,
            "index": index_val,
            "type": py_type,
            "cpp_type": cpp_type
        })
    
    print(f"Found {len(entries)} entries in ElsterTable")
    return entries


def parse_error_lists(content: str) -> Dict[str, List[Dict]]:
    """
    Parse error and operating mode lists from the header file.
    
    Args:
        content: Content of the ElsterTable.h file
        
    Returns:
        Dict mapping list names to their parsed entries
    """
    result = {}
    
    # Pattern to find static arrays of ErrorIndex type
    list_pattern = r'static\s+const\s+ErrorIndex\s+(\w+)\[\]\s*=\s*\{(.*?)\};'
    
    for match in re.finditer(list_pattern, content, re.DOTALL):
        list_name = match.group(1)
        list_content = match.group(2)
        
        entries = []
        # Parse individual entries
        entry_pattern = r'\{(0x[0-9a-fA-F]+|\d+)\s*,\s*"([^"]+)"\}'
        
        for entry_match in re.finditer(entry_pattern, list_content):
            code = entry_match.group(1)
            description = entry_match.group(2)
            
            # Convert hex format to int
            if code.startswith('0x'):
                code_val = int(code, 16)
            else:
                code_val = int(code)
                
            entries.append({
                "code": code_val,
                "description": description
            })
        
        result[list_name] = entries
        print(f"Found list {list_name} with {len(entries)} entries")
    
    return result


def generate_python_code(elster_table: List[Dict], error_lists: Dict[str, List[Dict]]) -> str:
    """
    Generate Python code for the parsed data.
    
    Args:
        elster_table: List of parsed ElsterIndex entries
        error_lists: Dictionary of parsed error and operating mode lists
        
    Returns:
        String containing the generated Python code
    """
    # Start with the file header and imports
    code = '''"""
ElsterTable module - contains the mapping of Stiebel Eltron signal codes.

This is a Python port of the original C++ implementation in ElsterTable.h.
Generated automatically by the convert_elster_table_improved.py script.
"""

from enum import Enum, auto


class ElsterType(Enum):
    """Enumeration of Elster value types."""
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


# Define the Elster table, a mapping of all known signals
ELSTER_TABLE = [
'''
    
    # Add ElsterTable entries
    for entry in elster_table:
        code += f"    ElsterIndex(\"{entry['name']}\", \"{entry['english_name']}\", {entry['index']}, {entry['type']}),\n"
    
    code += ''']

# Create lookup dictionaries for fast index lookups
ELSTER_INDEX_BY_NAME = {signal.name: signal for signal in ELSTER_TABLE}
ELSTER_INDEX_BY_ENGLISH_NAME = {signal.english_name: signal for signal in ELSTER_TABLE}
ELSTER_INDEX_BY_INDEX = {signal.index: signal for signal in ELSTER_TABLE}

'''

    # Add error and operating mode lists
    for list_name, entries in error_lists.items():
        # Convert CamelCase to SNAKE_CASE
        python_name = ''.join(['_' + c.lower() if c.isupper() else c for c in list_name]).lstrip('_').upper()
        
        code += f"# {list_name} from original C++ code\n{python_name} = {{\n"
        for entry in entries:
            code += f"    {entry['code']}: \"{entry['description']}\",\n"
        code += "}\n\n"
    
    # Add utility functions
    code += '''
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
    if value_type == ElsterType.ET_BOOLEAN:
        return bool(value)
    elif value_type == ElsterType.ET_TEMPERATURE:
        return value / 10  # Temperature values are scaled by 10
    elif value_type == ElsterType.ET_DOUBLE_VALUE or value_type == ElsterType.ET_TRIPLE_VALUE:
        return value / 10  # Double/triple values are scaled by 10
    elif value_type == ElsterType.ET_PERCENT:
        return value / 10  # Percent values are scaled by 10
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
    """
    if value_type == ElsterType.ET_BOOLEAN:
        return 1 if string_value.lower() in ["true", "1", "on", "yes"] else 0
    elif value_type == ElsterType.ET_TEMPERATURE:
        return int(float(string_value) * 10)  # Temperature values are scaled by 10
    elif value_type == ElsterType.ET_DOUBLE_VALUE or value_type == ElsterType.ET_TRIPLE_VALUE:
        return int(float(string_value) * 10)  # Double/triple values are scaled by 10
    elif value_type == ElsterType.ET_PERCENT:
        return int(float(string_value) * 10)  # Percent values are scaled by 10
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
'''
    
    return code


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Convert ElsterTable.h to Python format')
    parser.add_argument('--input', '-i', required=False,
                        default='../../stiebeltools/ElsterTable.h',
                        help='Path to ElsterTable.h input file')
    parser.add_argument('--output', '-o', required=False,
                        default='../stiebel_control/elster_table_converted.py',
                        help='Path to output Python file')
    args = parser.parse_args()
    
    # Resolve paths relative to the script location
    script_dir = Path(__file__).parent.absolute()
    input_file = Path(os.path.join(script_dir, args.input)).resolve()
    output_file = Path(os.path.join(script_dir, args.output)).resolve()
    
    print(f"Converting {input_file} to {output_file}")
    
    # Read the input file
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse the C++ content
    type_map = parse_elster_type_enum(content)
    elster_table = parse_elster_table(content, type_map)
    error_lists = parse_error_lists(content)
    
    # Generate Python code
    python_code = generate_python_code(elster_table, error_lists)
    
    # Create the output directory if it doesn't exist
    os.makedirs(output_file.parent, exist_ok=True)
    
    # Write the output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(python_code)
    
    print(f"Successfully converted {len(elster_table)} signals and {len(error_lists)} auxiliary lists")
    print(f"Output written to {output_file}")


if __name__ == '__main__':
    main()
