"""
Real implementation of BRGB (RGB LED) actuator using RPi.GPIO
Controls RGB LED colors based on IR remote commands
"""
import time
import threading

try:
    import RPi.GPIO as GPIO  # type: ignore
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    GPIO = None


class BRGB:
    """RGB LED controller"""
    
    def __init__(self, red_pin, green_pin, blue_pin):
        """
        Initialize RGB LED.
        
        Args:
            red_pin: GPIO pin for red LED (from settings.json)
            green_pin: GPIO pin for green LED (from settings.json)
            blue_pin: GPIO pin for blue LED (from settings.json)
        """
        if not GPIO_AVAILABLE:
            raise RuntimeError("RPi.GPIO is not available. This code must run on a Raspberry Pi.")
        
        self.red_pin = red_pin
        self.green_pin = green_pin
        self.blue_pin = blue_pin
        
        # Initialize GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.red_pin, GPIO.OUT)
        GPIO.setup(self.green_pin, GPIO.OUT)
        GPIO.setup(self.blue_pin, GPIO.OUT)
        
        # Turn off initially
        self.turn_off()
    
    def turn_off(self):
        """Turn off all LEDs"""
        GPIO.output(self.red_pin, GPIO.LOW)
        GPIO.output(self.green_pin, GPIO.LOW)
        GPIO.output(self.blue_pin, GPIO.LOW)
    
    def white(self):
        """Set white color (all LEDs on)"""
        GPIO.output(self.red_pin, GPIO.HIGH)
        GPIO.output(self.green_pin, GPIO.HIGH)
        GPIO.output(self.blue_pin, GPIO.HIGH)
    
    def red(self):
        """Set red color"""
        GPIO.output(self.red_pin, GPIO.HIGH)
        GPIO.output(self.green_pin, GPIO.LOW)
        GPIO.output(self.blue_pin, GPIO.LOW)
    
    def green(self):
        """Set green color"""
        GPIO.output(self.red_pin, GPIO.LOW)
        GPIO.output(self.green_pin, GPIO.HIGH)
        GPIO.output(self.blue_pin, GPIO.LOW)
    
    def blue(self):
        """Set blue color"""
        GPIO.output(self.red_pin, GPIO.LOW)
        GPIO.output(self.green_pin, GPIO.LOW)
        GPIO.output(self.blue_pin, GPIO.HIGH)
    
    def yellow(self):
        """Set yellow color (red + green)"""
        GPIO.output(self.red_pin, GPIO.HIGH)
        GPIO.output(self.green_pin, GPIO.HIGH)
        GPIO.output(self.blue_pin, GPIO.LOW)
    
    def purple(self):
        """Set purple color (red + blue)"""
        GPIO.output(self.red_pin, GPIO.HIGH)
        GPIO.output(self.green_pin, GPIO.LOW)
        GPIO.output(self.blue_pin, GPIO.HIGH)
    
    def light_blue(self):
        """Set light blue color (green + blue)"""
        GPIO.output(self.red_pin, GPIO.LOW)
        GPIO.output(self.green_pin, GPIO.HIGH)
        GPIO.output(self.blue_pin, GPIO.HIGH)
    
    def set_color_by_number(self, number):
        """
        Set color based on button number.
        
        Args:
            number: Button number (1-9, 0)
                   1 = off, 2 = white, 3 = red, 4 = green, 5 = blue,
                   6 = yellow, 7 = purple, 8 = light blue, 9 = red (repeat), 0 = off
        """
        color_map = {
            1: self.turn_off,
            2: self.white,
            3: self.red,
            4: self.green,
            5: self.blue,
            6: self.yellow,
            7: self.purple,
            8: self.light_blue,
            9: self.red,  # Repeat red
            0: self.turn_off  # Repeat off
        }
        
        if number in color_map:
            color_map[number]()
            return True
        return False
    
    def cleanup(self):
        """Cleanup GPIO resources"""
        try:
            self.turn_off()
            GPIO.cleanup()
        except Exception:
            pass
