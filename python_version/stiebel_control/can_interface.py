"""
CAN Interface module for Stiebel Eltron heat pump communication.

This module handles the communication with the heat pump using the CAN bus
via the python-can library.
"""

import time
import logging
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Callable, Any

import can
from can import Message

from stiebel_control.elster_table import (
    ElsterIndex, 
    get_elster_index_by_index, 
    get_elster_index_by_name,
    translate_value,
    translate_string_to_value,
    ElsterType
)

# Configure logger
logger = logging.getLogger(__name__)


@dataclass
class CanMember:
    """Represents a CAN bus member with its addressing information."""
    name: str
    can_id: int
    read_id: Tuple[int, int]
    write_id: Tuple[int, int]
    confirmation_id: Tuple[int, int] = (0, 0)


class CanInterface:
    """
    Interface for communication with Stiebel Eltron heat pumps via CAN bus.
    
    This class handles the protocol details specific to Stiebel Eltron heat pumps,
    including message formatting and parsing.
    """
    
    # Default CAN members definition based on the WPL13E configuration from the C++ code
    DEFAULT_CAN_MEMBERS = [
        # Name,        CAN ID,  Read ID,      Write ID,     Confirmation ID
        CanMember("ESPCLIENT", 0x680, (0x00, 0x00), (0x00, 0x00), (0xE2, 0x00)),  # The ESP Home Client
        CanMember("PUMP",      0x180, (0x31, 0x00), (0x30, 0x00), (0x00, 0x00)),
        CanMember("FE7X",      0x301, (0x61, 0x01), (0x00, 0x00), (0x00, 0x00)),
        CanMember("FEK",       0x302, (0x61, 0x02), (0x00, 0x00), (0x00, 0x00)),
        CanMember("MANAGER",   0x480, (0x91, 0x00), (0x90, 0x00), (0x00, 0x00)),
        CanMember("HEATING",   0x500, (0xA1, 0x00), (0xA0, 0x00), (0x00, 0x00)),  # Heating Module
        CanMember("FE7",       0x602, (0xC1, 0x02), (0x00, 0x00), (0x00, 0x00)),
    ]
    
    # CAN member indices for easier reference
    CM_ESPCLIENT = 0
    CM_PUMP = 1
    CM_FE7X = 2
    CM_FEK = 3
    CM_MANAGER = 4
    CM_HEATING = 5
    CM_FE7 = 6
    
    def __init__(self, can_interface: str = 'can0', 
                 can_members: List[CanMember] = None, 
                 bitrate: int = 20000, 
                 callback: Optional[Callable[[str, Any, int], None]] = None):
        """Initialize the CAN interface.
        
        Args:
            can_interface: Name of the CAN interface (e.g., 'can0')
            can_members: Optional list of CanMember objects; defaults to DEFAULT_CAN_MEMBERS
            bitrate: CAN bus bitrate, default is 20000 for Stiebel Eltron heat pumps
            callback: Optional callback function for value updates
        """
        self.can_interface = can_interface
        self.can_members = can_members or self.DEFAULT_CAN_MEMBERS
        self.bitrate = bitrate
        self.callback = callback
        self.bus = None
        self.running = False
        
        # Dictionary of pending requests, keyed by (can_id, index)
        self.pending_requests = {}
        
        # Dictionary to store latest values, keyed by (can_id, index)
        self.latest_values = {}
        
    def start(self):
        """Start the CAN interface."""
        try:
            self.bus = can.interface.Bus(
                channel=self.can_interface,
                bustype='socketcan',
                bitrate=self.bitrate
            )
            self.running = True
            logger.info(f"CAN interface started on {self.can_interface}")
            
            # Start the message receiver in a separate thread
            import threading
            self.receiver_thread = threading.Thread(
                target=self._receive_messages,
                daemon=True  # Allow the thread to exit when the main program exits
            )
            self.receiver_thread.start()
            logger.info("CAN message receiver thread started")
            
            return True
        except Exception as e:
            logger.error(f"Failed to start CAN interface: {e}")
            return False
    
    def stop(self):
        """Stop the CAN interface."""
        self.running = False
        if self.bus:
            self.bus.shutdown()
            self.bus = None
            logger.info("CAN interface stopped")
    
    def _receive_messages(self):
        """
        Start receiving CAN messages in a dedicated thread.
        This is typically run in a separate thread.
        """
        if not self.bus:
            logger.error("CAN bus not initialized")
            return
            
        while self.running:
            try:
                msg = self.bus.recv(timeout=1.0)
                if msg:
                    self._process_can_message(msg)
            except Exception as e:
                logger.error(f"Error receiving CAN message: {e}")
    
    def _process_can_message(self, msg: Message):
        """
        Process an incoming CAN message.
        
        Args:
            msg: CAN message received from the bus
        """
        try:
            can_id = msg.arbitration_id
            data = msg.data
            
            # Check message length
            if len(data) < 7:
                logger.debug(f"Ignoring short message from ID 0x{can_id:X}")
                return
                
            # Extract the index and value bytes from the message
            if data[2] == 0xFA:
                # Extended index format
                index = (data[3] << 8) + data[4]
                value_byte1 = data[5]
                value_byte2 = data[6]
            else:
                # Standard index format
                index = data[2]
                value_byte1 = data[3]
                value_byte2 = data[4]
            
            # Get the signal definition from the Elster table
            ei = get_elster_index_by_index(index)
            
            # Calculate the raw value
            raw_value = (value_byte1 << 8) + value_byte2
            
            # Translate the value according to its type
            typed_value = translate_value(raw_value, ei.type)
            
            # Log the received signal
            logger.debug(f"CAN 0x{can_id:X}: {ei.english_name} = {typed_value}")
            
            # Store the latest value
            request_key = (can_id, index)
            self.latest_values[request_key] = typed_value
            
            # If this is a response to a pending request, handle it
            if request_key in self.pending_requests:
                request_info = self.pending_requests.pop(request_key)
                # If there's a callback, invoke it
                if request_info.get('callback'):
                    request_info['callback'](typed_value)
            
            # If there's a global callback, invoke it with CAN ID
            # Pass the CAN ID so the callback can filter by it
            if self.callback:
                self.callback(ei.english_name, typed_value, can_id)
                
        except Exception as e:
            logger.error(f"Error processing CAN message: {e}")
    
    def read_signal(self, member_index: int, signal_name: str, callback: Optional[Callable] = None) -> bool:
        """
        Read a signal from a CAN member.
        
        Args:
            member_index: Index of the CAN member in the can_members list
            signal_name: Name of the signal to read (must exist in ElsterTable)
            callback: Optional callback for the response (will be called with the value)
            
        Returns:
            bool: True if the request was sent successfully, False otherwise
        """
        if not self.bus:
            logger.error("CAN bus not initialized")
            return False
            
        try:
            # Get the CAN member
            if member_index >= len(self.can_members):
                logger.error(f"Invalid CAN member index: {member_index}. Available members: {[m.name for m in self.can_members]}")
                return False
                
            member = self.can_members[member_index]
            
            # Get the signal definition
            ei = get_elster_index_by_name(signal_name)
            if ei.name == "UNKNOWN":
                logger.error(f"Unknown signal: {signal_name}")
                return False
                
            logger.debug(f"Preparing to read signal {signal_name} (index {ei.index}) from member {member.name} (CAN ID 0x{member.can_id:X})")
            
            # Create the request message
            index_byte1 = (ei.index >> 8) & 0xFF
            index_byte2 = ei.index & 0xFF
            
            # Format the message depending on whether we need an extended index
            if index_byte1 == 0:
                data = [
                    member.read_id[0],
                    member.read_id[1],
                    index_byte2,
                    0x00,
                    0x00,
                    0x00,
                    0x00
                ]
            else:
                data = [
                    member.read_id[0],
                    member.read_id[1],
                    0xFA,
                    index_byte1,
                    index_byte2,
                    0x00,
                    0x00
                ]
                
            # Create and send the CAN message
            msg = Message(
                arbitration_id=self.can_members[self.CM_ESPCLIENT].can_id,
                data=data,
                is_extended_id=False
            )
            
            # Register the pending request
            if callback:
                self.pending_requests[(member.can_id, ei.index)] = {
                    'callback': callback,
                    'timestamp': time.time()
                }
                
            self.bus.send(msg)
            logger.debug(f"Sent read request for {signal_name} to {member.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending read request: {e}")
            return False
            
    def write_signal(self, member_index: int, signal_name: str, value: Any) -> bool:
        """
        Write a value to a signal on a CAN member.
        
        Args:
            member_index: Index of the CAN member in the can_members list
            signal_name: Name of the signal to write to (must exist in ElsterTable)
            value: Value to write (will be converted according to the signal type)
            
        Returns:
            bool: True if the request was sent successfully, False otherwise
        """
        if not self.bus:
            logger.error("CAN bus not initialized")
            return False
            
        try:
            # Get the CAN member
            member = self.can_members[member_index]
            
            # Get the signal definition
            ei = get_elster_index_by_name(signal_name)
            if ei.name == "UNKNOWN":
                logger.error(f"Unknown signal: {signal_name}")
                return False
                
            # Convert the value to the raw format
            if isinstance(value, str):
                raw_value = translate_string_to_value(value, ei.type)
            else:
                raw_value = translate_string_to_value(str(value), ei.type)
                
            # Create the request message
            index_byte1 = (ei.index >> 8) & 0xFF
            index_byte2 = ei.index & 0xFF
            value_byte1 = (raw_value >> 8) & 0xFF
            value_byte2 = raw_value & 0xFF
            
            # Format the message depending on whether we need an extended index
            if index_byte1 == 0:
                data = [
                    member.write_id[0],
                    member.write_id[1],
                    index_byte2,
                    value_byte1,
                    value_byte2,
                    0x00,
                    0x00
                ]
            else:
                data = [
                    member.write_id[0],
                    member.write_id[1],
                    0xFA,
                    index_byte1,
                    index_byte2,
                    value_byte1,
                    value_byte2
                ]
                
            # Create and send the CAN message
            msg = Message(
                arbitration_id=self.can_members[self.CM_ESPCLIENT].can_id,
                data=data,
                is_extended_id=False
            )
            
            self.bus.send(msg)
            logger.debug(f"Sent write request for {signal_name}={value} to {member.name}")
            
            # After writing, we should read back the value to confirm
            self.read_signal(member_index, signal_name)
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending write request: {e}")
            return False
            
    def get_latest_value(self, member_index: int, signal_name: str, can_member_ids: List[int] = None) -> Optional[Any]:
        """
        Get the latest value for a signal.
        
        Args:
            member_index: Primary index of the CAN member
            signal_name: Name of the signal
            can_member_ids: Optional list of specific CAN IDs to check in addition to the primary member
            
        Returns:
            The latest value if available, None otherwise
        """
        try:
            ei = get_elster_index_by_name(signal_name)
            
            # First check the primary member
            member = self.can_members[member_index]
            value = self.latest_values.get((member.can_id, ei.index))
            if value is not None:
                return value
                
            # If a list of additional CAN IDs was provided, check those too
            if can_member_ids:
                for can_id in can_member_ids:
                    value = self.latest_values.get((can_id, ei.index))
                    if value is not None:
                        return value
                        
            # Fall back to primary member's value (which will be None at this point)
            return value
        except Exception as e:
            logger.error(f"Error getting latest value: {e}")
            return None
