"""
Real implementation of DUS2 (Door Ultrasonic Sensor) using RPi.GPIO
"""
import time
import threading

try:
    import RPi.GPIO as GPIO  # type: ignore
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    # GPIO not available (not on Raspberry Pi or not installed)
    GPIO_AVAILABLE = False
    GPIO = None


class DUS2:
    """Ultrasonic distance sensor (HC-SR04) controller"""
    
    def __init__(self, trig_pin=23, echo_pin=24):
        """
        Initialize ultrasonic sensor.
        
        Args:
            trig_pin: GPIO pin for trigger (default: 23)
            echo_pin: GPIO pin for echo (default: 24)
        """
        if not GPIO_AVAILABLE:
            raise RuntimeError("RPi.GPIO is not available. This code must run on a Raspberry Pi.")
        
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin
        
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.trig_pin, GPIO.OUT)
        GPIO.setup(self.echo_pin, GPIO.IN)
        
        # Ensure trigger is low initially
        GPIO.output(self.trig_pin, False)
        time.sleep(0.2)
    
    def get_distance(self):
        """
        Measure distance using ultrasonic sensor.
        
        Returns:
            Distance in cm, or None if measurement timed out
        """
        # Send trigger pulse
        GPIO.output(self.trig_pin, False)
        time.sleep(0.2)
        GPIO.output(self.trig_pin, True)
        time.sleep(0.00001)
        GPIO.output(self.trig_pin, False)
        
        pulse_start_time = time.time()
        pulse_end_time = time.time()
        
        max_iter = 100
        
        # Wait for echo to go high
        iter_count = 0
        while GPIO.input(self.echo_pin) == 0:
            if iter_count > max_iter:
                return None
            pulse_start_time = time.time()
            iter_count += 1
        
        # Wait for echo to go low
        iter_count = 0
        while GPIO.input(self.echo_pin) == 1:
            if iter_count > max_iter:
                return None
            pulse_end_time = time.time()
            iter_count += 1
        
        # Calculate distance
        pulse_duration = pulse_end_time - pulse_start_time
        distance = (pulse_duration * 34300) / 2  # Speed of sound = 343 m/s
        
        return distance
    
    def cleanup(self):
        """Clean up GPIO resources"""
        if GPIO_AVAILABLE:
            GPIO.cleanup()


def run_dus2_loop(dus2_instance, interval=1.0, callback=None, stop_event=None):
    """
    Run continuous loop reading distance sensor.
    
    Args:
        dus2_instance: DUS2 instance
        interval: Time between measurements in seconds
        callback: Function to call with distance value (receives distance in cm)
        stop_event: threading.Event to stop the loop
    """
    if stop_event is None:
        stop_event = threading.Event()
    
    try:
        while not stop_event.is_set():
            distance = dus2_instance.get_distance()
            if distance is not None:
                if callback:
                    callback(int(distance))
            else:
                if callback:
                    callback("Measurement timed out")
            
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print('\n[DUS2] Measurement stopped by user')
        dus2_instance.cleanup()
    except Exception as e:
        print(f'[DUS2] Error: {str(e)}')
        dus2_instance.cleanup()


if __name__ == '__main__':
    # Test code
    dus2 = DUS2()
    try:
        while True:
            distance = dus2.get_distance()
            if distance is not None:
                print(f'Distance: {distance} cm')
            else:
                print('Measurement timed out')
            time.sleep(1)
    except KeyboardInterrupt:
        dus2.cleanup()
        print('Measurement stopped by user')
    except Exception as e:
        print(f'Error: {str(e)}')
