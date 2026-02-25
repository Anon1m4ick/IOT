"""
Real implementation of IR (Infrared Receiver) sensor using RPi.GPIO
Reads commands from IR remote control
"""
import time
import threading
from datetime import datetime

try:
    import RPi.GPIO as GPIO  # type: ignore
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    GPIO = None


class IR:
    """IR receiver controller for reading remote control commands"""
    
    # Button codes (HEX)
    BUTTONS = [
        0x300ff22dd, 0x300ffc23d, 0x300ff629d, 0x300ffa857, 0x300ff9867,
        0x300ffb04f, 0x300ff6897, 0x300ff02fd, 0x300ff30cf, 0x300ff18e7,
        0x300ff7a85, 0x300ff10ef, 0x300ff38c7, 0x300ff5aa5, 0x300ff42bd,
        0x300ff4ab5, 0x300ff52ad
    ]
    
    # Button names
    BUTTON_NAMES = [
        "LEFT", "RIGHT", "UP", "DOWN", "2", "3", "1", "OK",
        "4", "5", "6", "7", "8", "9", "*", "0", "#"
    ]
    
    # Mapping: button name -> button number (for BRGB control)
    BUTTON_TO_NUMBER = {
        "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
        "6": 6, "7": 7, "8": 8, "9": 9, "0": 0
    }
    
    def __init__(self, pin):
        """
        Initialize IR receiver.
        
        Args:
            pin: GPIO pin for IR receiver (from settings.json)
        """
        if not GPIO_AVAILABLE:
            raise RuntimeError("RPi.GPIO is not available. This code must run on a Raspberry Pi.")
        
        self.pin = pin
        
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN)
    
    def _get_binary(self):
        """
        Get binary value from IR signal.
        
        Returns:
            Binary value as integer
        """
        num1s = 0  # Number of consecutive 1s read
        binary = 1  # The binary value
        command = []  # The list to store pulse times in
        previous_value = 0  # The last value
        value = GPIO.input(self.pin)  # The current value
        
        # Waits for the sensor to pull pin low
        while value:
            time.sleep(0.0001)  # This sleep decreases CPU utilization immensely
            value = GPIO.input(self.pin)
        
        # Records start time
        start_time = datetime.now()
        
        while True:
            # If change detected in value
            if previous_value != value:
                now = datetime.now()
                pulse_time = now - start_time  # Calculate the time of pulse
                start_time = now  # Reset start time
                command.append((previous_value, pulse_time.microseconds))  # Store recorded data
            
            # Updates consecutive 1s variable
            if value:
                num1s += 1
            else:
                num1s = 0
            
            # Breaks program when the amount of 1s surpasses 10000
            if num1s > 10000:
                break
            
            # Re-reads pin
            previous_value = value
            value = GPIO.input(self.pin)
        
        # Converts times to binary
        for (typ, tme) in command:
            if typ == 1:  # If looking at rest period
                if tme > 1000:  # If pulse greater than 1000us
                    binary = binary * 10 + 1  # Must be 1
                else:
                    binary *= 10  # Must be 0
        
        if len(str(binary)) > 34:  # Sometimes, there is some stray characters
            binary = int(str(binary)[:34])
        
        return binary
    
    def _convert_hex(self, binary_value):
        """
        Convert binary value to hex.
        
        Args:
            binary_value: Binary value as integer
            
        Returns:
            Hex value as string
        """
        tmp_b2 = int(str(binary_value), 2)  # Temporarily proper base 2
        return hex(tmp_b2)
    
    def read_command(self):
        """
        Read command from IR remote.
        
        Returns:
            Button name (string) or None if no valid command
        """
        try:
            in_data = self._convert_hex(self._get_binary())  # Get incoming hex value
            for button in range(len(self.BUTTONS)):  # Run through every value in list
                if hex(self.BUTTONS[button]) == in_data:  # Check against incoming
                    return self.BUTTON_NAMES[button]  # Return corresponding button name
        except Exception as e:
            print(f"[IR] Error reading command: {e}")
            return None
        
        return None
    
    def cleanup(self):
        """Cleanup GPIO resources"""
        try:
            GPIO.cleanup()
        except Exception:
            pass


def run_ir_loop(ir_instance, callback, stop_event):
    """
    Main loop for IR sensor.
    
    Args:
        ir_instance: IR instance
        callback: Callback function to call with button name
        stop_event: Threading event to stop the loop
    """
    while not stop_event.is_set():
        try:
            button = ir_instance.read_command()
            if button:
                callback(button)
            time.sleep(0.1)  # Small delay between reads
        except Exception as e:
            print(f"[IR] Error in sensor loop: {e}")
            time.sleep(1)
    
    # Cleanup on exit
    try:
        ir_instance.cleanup()
    except Exception:
        pass
