"""
BRGB component - RGB LED actuator controlled by IR remote
Button mapping:
  0 = OFF, 1 = WHITE, 2 = RED, 3 = GREEN, 4 = BLUE,
  5 = YELLOW, 6 = PURPLE, 7 = LIGHT_BLUE, 8 = OFF, 9 = WHITE
"""
import threading
from simulators.brgb import set_color_by_number, get_brgb_color


def brgb_callback(message):
    """Default callback for BRGB updates"""
    print(f"BRGB: {message}")


def run_brgb(settings, threads, stop_event, callback=None, mqtt_publisher=None):
    """
    Run BRGB component.
    
    Args:
        settings: BRGB settings from settings.json
        threads: List to append thread to
        stop_event: Event to stop the thread
        callback: Optional callback for color changes
        mqtt_publisher: Optional MQTT publisher
    
    Returns:
        Handler function for IR button presses
    """
    if callback is None:
        callback = brgb_callback
    
    def handle_ir_button(button_name):
        """Handle IR button press and change BRGB color"""
        # Map button name to number
        button_to_number = {
            "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
            "6": 6, "7": 7, "8": 8, "9": 9, "0": 0
        }
        
        if button_name in button_to_number:
            number = button_to_number[button_name]
            
            if settings['simulated']:
                # Simulator
                set_color_by_number(number)
                color_name = get_brgb_color()
                message = f"Color changed to {color_name} (button {number})"
            else:
                # Real hardware
                from actuators.brgb import BRGB
                # Get or create BRGB instance
                if not hasattr(run_brgb, '_brgb_instance'):
                    red_pin = settings.get('red_pin', 12)
                    green_pin = settings.get('green_pin', 13)
                    blue_pin = settings.get('blue_pin', 19)
                    run_brgb._brgb_instance = BRGB(red_pin, green_pin, blue_pin)
                
                run_brgb._brgb_instance.set_color_by_number(number)
                color_map = {
                    0: "OFF", 1: "WHITE", 2: "RED", 3: "GREEN", 4: "BLUE",
                    5: "YELLOW", 6: "PURPLE", 7: "LIGHT_BLUE", 8: "OFF", 9: "WHITE"
                }
                color_name = color_map.get(number, "UNKNOWN")
                message = f"Color changed to {color_name} (button {number})"
            
            # Send to MQTT
            if mqtt_publisher:
                # Send color name as string value
                mqtt_publisher.add_sensor_data("BRGB", color_name, settings['simulated'])
            
            callback(message)
    
    if settings['simulated']:
        print("Starting BRGB simulator")
        # For simulator, we just wait - color changes will be triggered by IR
        print("BRGB simulator ready (waiting for IR commands)")
    else:
        print("Starting BRGB real hardware")
        # Initialize BRGB instance
        red_pin = settings.get('red_pin', 12)
        green_pin = settings.get('green_pin', 13)
        blue_pin = settings.get('blue_pin', 19)
        run_brgb._brgb_instance = BRGB(red_pin, green_pin, blue_pin)
        print("BRGB real hardware ready (waiting for IR commands)")
    
    # Return handler function so IR component can use it
    return handle_ir_button
