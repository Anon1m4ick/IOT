"""
Real implementation of DPIR3 (Living Room Motion Sensor) using RPi.GPIO
"""
import time
import threading

try:
    import RPi.GPIO as GPIO  # type: ignore
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    GPIO = None


class DPIR3:
    """Motion sensor (PIR) controller"""
    
    def __init__(self, pin):
        """
        Initialize motion sensor.
        
        Args:
            pin: GPIO pin for PIR sensor (from settings.json)
        """
        if not GPIO_AVAILABLE:
            raise RuntimeError("RPi.GPIO is not available. This code must run on a Raspberry Pi.")
        
        self.pin = pin
        self.motion_detected = False
        
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN)
        
        # Setup event detection
        # GPIO.add_event_detect(self.pin, GPIO.RISING, callback=self._motion_detected_callback, bouncetime=300)
        # GPIO.add_event_detect(self.pin, GPIO.FALLING, callback=self._no_motion_callback, bouncetime=300)
        GPIO.add_event_detect(self.pin, GPIO.BOTH, callback=self._on_edge, bouncetime=300)
    

    def _on_edge(self, channel):
        self.motion_detected = bool(GPIO.input(channel))

    # def _motion_detected_callback(self, channel):
    #     """Callback for motion detected (RISING edge)"""
    #     self.motion_detected = True
    
    # def _no_motion_callback(self, channel):
    #     """Callback for no motion (FALLING edge)"""
    #     self.motion_detected = False
    
    def get_state(self):
        """Get current motion state (1 = detected, 0 = no motion)"""
        return 1 if self.motion_detected else 0
    
    def cleanup(self):
        """Clean up GPIO resources"""
        if GPIO_AVAILABLE:
            GPIO.remove_event_detect(self.pin)
            GPIO.cleanup()


def run_dpir3_loop(dpir3_instance, interval=0.5, callback=None, stop_event=None):
    """
    Run continuous loop monitoring motion sensor.
    
    Args:
        dpir3_instance: DPIR3 instance
        interval: Time between checks in seconds
        callback: Function to call when motion state changes
        stop_event: threading.Event to stop the loop
    """
    if stop_event is None:
        stop_event = threading.Event()
    
    previous_state = None
    
    try:
        while not stop_event.is_set():
            current_state = dpir3_instance.get_state()
            
            # Only trigger callback on state change
            if previous_state is not None and previous_state != current_state:
                if current_state == 1:
                    if callback:
                        callback("Motion detected")
                else:
                    if callback:
                        callback("Motion stopped")
            
            previous_state = current_state
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print('\n[DPIR3] Stopped by user')
        dpir3_instance.cleanup()
    except Exception as e:
        print(f'[DPIR3] Error: {str(e)}')
        dpir3_instance.cleanup()
