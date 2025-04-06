#!/usr/bin/env python3
"""
Improved Conversion tool to convert ElsterTable.h (C++ format) to YAML format.

This script extracts the signal definitions from the ElsterTable.h file
and generates a YAML file with all signal definitions (for configuration).
The Python module will load this YAML file during initialization.
"""

import os
import re
import yaml
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
    
    # Create a mapping from C++ type to Python type
    type_mapping = {
        'et_default': 'ET_INTEGER',          # Plain integer values
        'et_dec_val': 'ET_TEMPERATURE',      # Values with 1 decimal place (typically temperatures)
        'et_cent_val': 'ET_PERCENT',         # Values with 2 decimal places (typically percentages)
        'et_mil_val': 'ET_TRIPLE_VALUE',     # Values with 3 decimal places
        'et_byte': 'ET_INTEGER',             # Byte values (8-bit integers)
        'et_bool': 'ET_BOOLEAN',             # Boolean values (0x0001/0x0000)
        'et_little_bool': 'ET_BOOLEAN',      # Boolean values in different format (0x0100/0x0000)
        'et_double_val': 'ET_DOUBLE_VALUE',  # Values with 3 decimal places
        'et_triple_val': 'ET_TRIPLE_VALUE',  # Values with 6 decimal places
        'et_little_endian': 'ET_INTEGER',    # Byte-swapped integers
        'et_betriebsart': 'ET_PROGRAM_SWITCH', # Operation modes
        'et_zeit': 'ET_HOUR',                # Time values (HH:MM)
        'et_datum': 'ET_DATE',               # Date values (DD.MM)
        'et_time_domain': 'ET_INTEGER',      # Time ranges with special formatting
        'et_dev_nr': 'ET_INTEGER',           # Device numbers
        'et_err_nr': 'ET_INTEGER',           # Error codes
        'et_dev_id': 'ET_INTEGER'            # Device IDs
    }
    
    return type_mapping


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
        py_type = type_map.get(cpp_type, "ET_NONE")  # Default to ET_NONE if type not found
        
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


def generate_yaml(elster_table: List[Dict], output_path: str) -> None:
    """
    Generate a YAML file with all Elster signal definitions.
    
    Args:
        elster_table: List of parsed ElsterIndex entries
        output_path: Path to write the YAML file
    """
    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Prepare data for YAML export
    yaml_data = []
    for entry in elster_table:
        yaml_data.append({
            "name": entry["name"],
            "english_name": entry["english_name"],
            "index": entry["index"],
            "type": entry["type"]
        })
    
    # Write to YAML file
    with open(output_path, 'w') as f:
        yaml.safe_dump(yaml_data, f, default_flow_style=False, sort_keys=False)
    
    print(f"Generated YAML file with {len(yaml_data)} signal definitions: {output_path}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Convert ElsterTable.h to YAML format'
    )
    parser.add_argument(
        '--input', '-i',
        default='ElsterTable.h',
        help='Input ElsterTable.h file path'
    )
    parser.add_argument(
        '--yaml-output', '-y',
        default='../config/elster_signals.yaml',
        help='Output YAML file path'
    )
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"Input file not found: {args.input}")
        return 1
    
    # Read the header file
    with open(args.input, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse the header file
    type_map = parse_elster_type_enum(content)
    elster_table = parse_elster_table(content, type_map)
    
    # Generate output files
    generate_yaml(elster_table, args.yaml_output)
    
    print(f"Successfully converted {len(elster_table)} signals to YAML format.")
    return 0


if __name__ == '__main__':
    main()
