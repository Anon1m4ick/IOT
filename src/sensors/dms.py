"""
Real implementation of DMS (Door Membrane Switch / Keypad) using RPi.GPIO
"""
import time
import threading

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    # GPIO not available (not on Raspberry Pi or not installed)
    GPIO_AVAILABLE = False
    GPIO = None


class DMS:
    """Keypad controller using GPIO pins"""
    
    def __init__(self, rows=None, cols=None):
        """
        Initialize DMS keypad.
        
        Args:
            rows: List of 4 GPIO pins for rows [R1, R2, R3, R4]
                  Default: [25, 8, 7, 1]
            cols: List of 4 GPIO pins for columns [C1, C2, C3, C4]
                  Default: [12, 16, 20, 21]
        """
        if not GPIO_AVAILABLE:
            raise RuntimeError("RPi.GPIO is not available. This code must run on a Raspberry Pi.")
        
        # Default pins from user's code
        self.rows = rows if rows is not None else [25, 8, 7, 1]
        self.cols = cols if cols is not None else [12, 16, 20, 21]
        
        # Keypad layout
        self.keypad = [
            ['1', '2', '3', 'A'],
            ['4', '5', '6', 'B'],
            ['7', '8', '9', 'C'],
            ['*', '0', '#', 'D']
        ]
        
        # Initialize GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        
        # Setup row pins as outputs
        for row in self.rows:
            GPIO.setup(row, GPIO.OUT)
        
        # Setup column pins as inputs with pull-down resistors
        for col in self.cols:
            GPIO.setup(col, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    
    def read_line(self, line_index):
        """
        Read a single row of the keypad.
        
        Args:
            line_index: Index of the row (0-3)
        
        Returns:
            Character if button pressed, None otherwise
        """
        row_pin = self.rows[line_index]
        characters = self.keypad[line_index]
        
        GPIO.output(row_pin, GPIO.HIGH)
        
        button_pressed = None
        if GPIO.input(self.cols[0]) == 1:
            button_pressed = characters[0]
        elif GPIO.input(self.cols[1]) == 1:
            button_pressed = characters[1]
        elif GPIO.input(self.cols[2]) == 1:
            button_pressed = characters[2]
        elif GPIO.input(self.cols[3]) == 1:
            button_pressed = characters[3]
        
        GPIO.output(row_pin, GPIO.LOW)
        
        return button_pressed
    
    def read_keypad(self):
        """
        Read all rows of the keypad.
        
        Returns:
            Character if button pressed, None otherwise
        """
        for i in range(len(self.rows)):
            button = self.read_line(i)
            if button is not None:
                return button
        return None
    
    def cleanup(self):
        """Clean up GPIO resources"""
        if GPIO_AVAILABLE:
            GPIO.cleanup()


def run_dms_loop(dms_instance, interval=0.2, callback=None, stop_event=None):
    """
    Run continuous loop reading keypad.
    
    Args:
        dms_instance: DMS instance
        interval: Time between reads in seconds
        callback: Function to call when button is pressed (receives button character)
        stop_event: threading.Event to stop the loop
    """
    if stop_event is None:
        stop_event = threading.Event()
    
    last_button = None
    
    try:
        while not stop_event.is_set():
            button = dms_instance.read_keypad()
            
            # Only trigger callback on new button press (debouncing)
            if button is not None and button != last_button:
                if callback:
                    callback(f"Button pressed: {button}")
                last_button = button
            elif button is None:
                last_button = None
            
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print("\n[DMS] Application stopped!")
    except Exception as e:
        print(f"[DMS] Error: {e}")
    finally:
        dms_instance.cleanup()


if __name__ == '__main__':
    # Test code
    dms = DMS()
    try:
        while True:
            button = dms.read_keypad()
            if button is not None:
                print(f"Button pressed: {button}")
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nApplication stopped!")
        dms.cleanup()
