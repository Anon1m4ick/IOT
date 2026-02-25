"""
LCD component - displays DHT1, DHT2, DHT3 temperature and humidity with rotation
"""
import threading
from simulators.lcd import run_lcd_simulator


def lcd_callback(message):
    """Default callback for LCD updates"""
    print(f"LCD: {message}")


def run_lcd(settings, threads, stop_event, callback=None, mqtt_publisher=None):
    """
    Run LCD component.
    
    Args:
        settings: LCD settings from settings.json
        threads: List to append thread to
        stop_event: Event to stop the thread
        callback: Optional callback for display updates
        mqtt_publisher: Optional MQTT publisher (not used for LCD)
    """
    if callback is None:
        callback = lcd_callback
    
    rotation_interval = settings.get('rotation_interval', 3)  # Default 3 seconds
    
    if settings['simulated']:
        print("Starting LCD simulator")
        lcd_thread = threading.Thread(
            target=run_lcd_simulator,
            args=(rotation_interval, callback, stop_event)
        )
        lcd_thread.start()
        threads.append(lcd_thread)
        print("LCD simulator started")
    else:
        from actuators.lcd import run_lcd_loop, LCD
        print("Starting LCD real hardware")
        address = settings.get('i2c_address', None)  # Optional I2C address
        lcd = LCD(address=address)
        lcd_thread = threading.Thread(
            target=run_lcd_loop,
            args=(lcd, rotation_interval, stop_event)
        )
        lcd_thread.start()
        threads.append(lcd_thread)
        print("LCD real hardware started")
