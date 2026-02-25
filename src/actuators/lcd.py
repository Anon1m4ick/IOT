"""
Real implementation of LCD display using PCF8574 and Adafruit LCD1602
Displays temperature and humidity from DHT1, DHT2, DHT3 with rotation
"""
import time
import threading
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from drivers.pcf8574 import PCF8574_GPIO
from drivers.adafruit_lcd1602 import Adafruit_CharLCD
from dht_data_store import get_dht_data

# I2C addresses for PCF8574
PCF8574_address = 0x27
PCF8574A_address = 0x3F


class LCD:
    """16x2 LCD display controller"""
    
    def __init__(self, address=None):
        """
        Initialize LCD display.
        
        Args:
            address: I2C address (0x27 or 0x3F). If None, tries both.
        """
        # Try to create PCF8574 GPIO adapter
        mcp = None
        if address:
            try:
                mcp = PCF8574_GPIO(address)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize PCF8574 at address {hex(address)}: {e}")
        else:
            # Try default address first
            try:
                mcp = PCF8574_GPIO(PCF8574_address)
            except Exception:
                try:
                    mcp = PCF8574_GPIO(PCF8574A_address)
                except Exception as e:
                    raise RuntimeError(f"I2C Address Error! Failed to initialize PCF8574: {e}")
        
        self.mcp = mcp
        
        # Create LCD, passing in MCP GPIO adapter
        # pin_rs=0, pin_e=2, pins_db=[4,5,6,7] as per example
        self.lcd = Adafruit_CharLCD(pin_rs=0, pin_e=2, pins_db=[4, 5, 6, 7], GPIO=mcp)
        
        # Turn on LCD backlight
        self.mcp.output(3, 1)
        
        # Initialize LCD
        self.lcd.begin(16, 2)
    
    def clear(self):
        """Clear LCD display"""
        self.lcd.clear()
    
    def display_text(self, line1, line2=""):
        """
        Display text on LCD (2 lines, 16 characters each)
        
        Args:
            line1: First line text (max 16 chars)
            line2: Second line text (max 16 chars)
        """
        self.lcd.clear()
        self.lcd.setCursor(0, 0)
        self.lcd.message(line1[:16])  # Limit to 16 chars
        if line2:
            self.lcd.setCursor(0, 1)
            self.lcd.message(line2[:16])  # Limit to 16 chars
    
    def cleanup(self):
        """Cleanup LCD resources"""
        try:
            self.lcd.clear()
            self.mcp.output(3, 0)  # Turn off backlight
        except Exception:
            pass


def run_lcd_loop(lcd_instance, rotation_interval, stop_event):
    """
    Main loop for LCD display.
    Rotates between DHT1, DHT2, DHT3 every rotation_interval seconds.
    
    Args:
        lcd_instance: LCD instance
        rotation_interval: Seconds to display each DHT before rotating
        stop_event: Threading event to stop the loop
    """
    dht_sensors = ['DHT1', 'DHT2', 'DHT3']
    current_index = 0
    
    while not stop_event.is_set():
        try:
            # Get current DHT sensor data
            dht_id = dht_sensors[current_index]
            data = get_dht_data(dht_id)
            
            if data and data.get('humidity') is not None and data.get('temperature') is not None:
                humidity = data['humidity']
                temperature = data['temperature']
                
                # Format display text
                line1 = f"{dht_id}: T:{temperature:.1f}C H:{humidity:.1f}%"
                
                lcd_instance.display_text(line1)
            else:
                # No data available for this sensor
                line1 = f"{dht_id}: No data"
                lcd_instance.display_text(line1)
            
            # Rotate to next sensor after rotation_interval seconds
            for _ in range(int(rotation_interval * 10)):  # Check every 0.1 seconds
                if stop_event.is_set():
                    break
                time.sleep(0.1)
            
            # Move to next sensor
            current_index = (current_index + 1) % len(dht_sensors)
            
        except Exception as e:
            print(f"[LCD] Error in display loop: {e}")
            time.sleep(1)
    
    # Cleanup on exit
    try:
        lcd_instance.cleanup()
    except Exception:
        pass
