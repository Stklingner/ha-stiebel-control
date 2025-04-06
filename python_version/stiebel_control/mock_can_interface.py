"""
Mock CAN Interface for Stiebel Eltron heat pump control.

This module provides a simulated CAN interface for testing and debugging
without requiring actual hardware connections.
"""

import logging
import random
import threading
import time
from typing import Dict, List, Callable, Any, Tuple

from . import elster_table

logger = logging.getLogger(__name__)


class MockCANInterface:
    """
    A mock implementation of the CAN interface for testing without hardware.
    
    This class simulates the behavior of a Stiebel Eltron heat pump's CAN bus
    by providing mock responses to messages and generating periodic updates.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the mock CAN interface.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.interface_name = config.get('can', {}).get('interface', 'vcan0')
        self.bitrate = config.get('can', {}).get('bitrate', 20000)
        self.connected = False
        self.running = False
        self.mock_values = {}
        self._initialize_mock_values()
        self.message_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.simulation_thread = None
        self.update_interval = 2  # seconds between simulated messages
        
        # Enable more detailed debug logs if we're in debug mode
        self.debug_mode = config.get('debug', {}).get('enabled', False)
        if self.debug_mode:
            logger.setLevel(logging.DEBUG)

    def _initialize_mock_values(self):
        """Initialize the mock values for common signals."""
        # Common temperatures
        self.mock_values[0x000c] = 35  # AUSSENTEMP (Outside temp) - 3.5°C
        self.mock_values[0x000e] = 480  # SPEICHERISTTEMP (DHW temp) - 48.0°C
        self.mock_values[0x000f] = 350  # VORLAUFISTTEMP (Flow temp) - 35.0°C
        self.mock_values[0x0016] = 300  # RUECKLAUFISTTEMP (Return temp) - 30.0°C
        
        # Energy values
        self.mock_values[0x030] = 150  # HEIZLEISTUNG_TAG_KWH - 15.0 kWh
        self.mock_values[0x034] = 50   # EL_AUFNAHMELEISTUNG_HEIZEN_TAG_KWH - 5.0 kWh
        self.mock_values[0x038] = 30   # EL_AUFNAHMELEISTUNG_WW_TAG_KWH - 3.0 kWh
        
        # Operating status
        self.mock_values[0x0112] = 0    # Program switch - Emergency
        self.mock_values[0x0099] = 3    # Pump status - Running
        self.mock_values[0x0098] = 7    # Heat pump status
        
        # Add more mock values as needed
        
    def connect(self) -> bool:
        """
        Simulate connecting to the CAN interface.
        
        Returns:
            True if connection was successful, False otherwise
        """
        logger.info(f"[MOCK] Connecting to mock CAN interface {self.interface_name}")
        self.connected = True
        return True
        
    def disconnect(self) -> None:
        """Simulate disconnecting from the CAN interface."""
        logger.info("[MOCK] Disconnecting from mock CAN interface")
        self.stop_simulation()
        self.connected = False
        
    def is_connected(self) -> bool:
        """
        Check if the interface is connected.
        
        Returns:
            True if connected, False otherwise
        """
        return self.connected
        
    def register_message_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Register a callback for received messages.
        
        Args:
            callback: Function to call when a message is received
        """
        self.message_callbacks.append(callback)
        
    def start_simulation(self) -> None:
        """Start the simulation thread to generate mock data."""
        if self.simulation_thread is not None and self.simulation_thread.is_alive():
            return
            
        self.running = True
        self.simulation_thread = threading.Thread(
            target=self._simulation_loop,
            daemon=True
        )
        self.simulation_thread.start()
        logger.info("[MOCK] Started CAN simulation thread")
        
    def stop_simulation(self) -> None:
        """Stop the simulation thread."""
        self.running = False
        if self.simulation_thread is not None:
            self.simulation_thread.join(timeout=1.0)
            self.simulation_thread = None
        logger.info("[MOCK] Stopped CAN simulation thread")
        
    def _simulation_loop(self) -> None:
        """Main simulation loop that generates mock data."""
        while self.running:
            try:
                # Add small random fluctuations to temperatures
                for temp_idx in [0x000c, 0x000e, 0x000f, 0x0016]:
                    # Add random fluctuation of +/- 5 (0.5°C)
                    self.mock_values[temp_idx] += random.randint(-5, 5)
                    
                # Simulate a few messages
                self._simulate_message("PUMP", 0x000c)  # Outside temp
                self._simulate_message("PUMP", 0x000e)  # DHW temp
                self._simulate_message("PUMP", 0x000f)  # Flow temp
                self._simulate_message("PUMP", 0x0016)  # Return temp
                self._simulate_message("MANAGER", 0x0112) # Program switch
                
                # Simulate some energy values increasing over time
                self.mock_values[0x030] += random.randint(0, 2)  # HEIZLEISTUNG_TAG_KWH
                self.mock_values[0x034] += random.randint(0, 1)  # EL_AUFNAHMELEISTUNG_HEIZEN_TAG_KWH
                self._simulate_message("PUMP", 0x030)
                self._simulate_message("PUMP", 0x034)
                
                # Sleep for update interval
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"[MOCK] Error in simulation loop: {e}")
                time.sleep(5)  # Wait longer if there's an error
                
    def _simulate_message(self, can_member: str, signal_index: int) -> None:
        """
        Simulate a CAN message.
        
        Args:
            can_member: CAN member name (MANAGER, PUMP, etc.)
            signal_index: Signal index from ElsterTable
        """
        if signal_index not in self.mock_values:
            logger.warning(f"[MOCK] No mock value for signal index {signal_index}")
            return
            
        signal = elster_table.get_elster_index_by_index(signal_index)
        
        # Create a mock message
        message = {
            'can_id': signal_index,
            'member': can_member,
            'signal': signal.name,
            'value': self.mock_values[signal_index],
            'human_value': elster_table.translate_value(
                self.mock_values[signal_index], 
                signal.type
            ),
            'timestamp': time.time()
        }
        
        # Log the message if in debug mode
        if self.debug_mode:
            readable_value = elster_table.translate_value(
                self.mock_values[signal_index], 
                signal.type
            )
            logger.debug(f"[MOCK] Simulated message: {can_member}.{signal.name} = {readable_value}")
            
        # Call the registered callbacks
        for callback in self.message_callbacks:
            try:
                callback(message)
            except Exception as e:
                logger.error(f"[MOCK] Error in callback: {e}")
                
    def send_message(self, member: str, signal_name: str, value: Any) -> bool:
        """
        Simulate sending a message on the CAN bus.
        
        Args:
            member: CAN member name (MANAGER, PUMP, etc.)
            signal_name: Signal name as defined in ElsterTable
            value: Value to send
            
        Returns:
            True if the message was sent successfully, False otherwise
        """
        signal = elster_table.get_elster_index_by_name(signal_name)
        if signal.name == "UNKNOWN":
            logger.error(f"[MOCK] Unknown signal name: {signal_name}")
            return False
            
        # Convert the value based on signal type
        raw_value = elster_table.translate_string_to_value(str(value), signal.type)
        
        # Update the mock value
        self.mock_values[signal.index] = raw_value
        
        if self.debug_mode:
            readable_value = elster_table.translate_value(raw_value, signal.type)
            logger.debug(f"[MOCK] Sent message: {member}.{signal_name} = {readable_value}")
            
        # Simulate the response
        self._simulate_message(member, signal.index)
        
        return True
        
    def query_signal(self, member: str, signal_name: str) -> Tuple[bool, Any]:
        """
        Query the current value of a signal.
        
        Args:
            member: CAN member name (MANAGER, PUMP, etc.)
            signal_name: Signal name as defined in ElsterTable
            
        Returns:
            Tuple of (success, value) where success is a boolean and
            value is the current value of the signal (or None if not successful)
        """
        signal = elster_table.get_elster_index_by_name(signal_name)
        if signal.name == "UNKNOWN":
            logger.error(f"[MOCK] Unknown signal name: {signal_name}")
            return (False, None)
            
        if signal.index not in self.mock_values:
            # Create a random value for this signal
            if signal.type == elster_table.ElsterType.ET_TEMPERATURE:
                self.mock_values[signal.index] = random.randint(150, 450)  # 15.0 - 45.0°C
            elif signal.type == elster_table.ElsterType.ET_BOOLEAN:
                self.mock_values[signal.index] = random.randint(0, 1)
            elif signal.type == elster_table.ElsterType.ET_PROGRAM_SWITCH:
                self.mock_values[signal.index] = random.randint(0, 5)
            else:
                self.mock_values[signal.index] = random.randint(0, 1000)
                
        raw_value = self.mock_values[signal.index]
        readable_value = elster_table.translate_value(raw_value, signal.type)
        
        if self.debug_mode:
            logger.debug(f"[MOCK] Queried signal: {member}.{signal_name} = {readable_value}")
            
        return (True, readable_value)
