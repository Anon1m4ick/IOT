"""
Real implementation of GSG (Gyroscope Sensor) using MPU6050
Detects significant movement and returns 0 or 1
"""
import time
import threading
import math

try:
    from drivers.mpu6050_simple import MPU6050_Simple
    MPU6050_AVAILABLE = True
except (ImportError, RuntimeError):
    MPU6050_AVAILABLE = False
    MPU6050_Simple = None


class GSG:
    """Gyroscope sensor controller for motion detection"""
    
    def __init__(self, threshold=2000, calibration_samples=10):
        """
        Initialize GSG sensor.
        
        Args:
            threshold: Movement threshold (default 2000)
                       Higher value = less sensitive
            calibration_samples: Number of samples for baseline calibration
        """
        if not MPU6050_AVAILABLE:
            raise RuntimeError("MPU6050 is not available. This code must run on a Raspberry Pi with MPU6050 connected.")
        
        self.mpu = MPU6050_Simple()
        self.threshold = threshold
        self.calibration_samples = calibration_samples
        
        # Calibrate baseline
        self.baseline = self._calibrate()
    
    def _calibrate(self):
        """
        Calibrate baseline acceleration (when sensor is at rest).
        
        Returns:
            Baseline magnitude value
        """
        samples = []
        for _ in range(self.calibration_samples):
            accel = self.mpu.get_acceleration()
            magnitude = math.sqrt(accel[0]**2 + accel[1]**2 + accel[2]**2)
            samples.append(magnitude)
            time.sleep(0.1)
        
        # Return average baseline
        return sum(samples) / len(samples)
    
    def detect_movement(self):
        """
        Detect significant movement.
        
        Returns:
            1 if significant movement detected, 0 otherwise
        """
        accel = self.mpu.get_acceleration()
        
        # Calculate magnitude of acceleration vector
        magnitude = math.sqrt(accel[0]**2 + accel[1]**2 + accel[2]**2)
        
        # Calculate difference from baseline
        difference = abs(magnitude - self.baseline)
        
        # Return 1 if difference exceeds threshold
        return 1 if difference > self.threshold else 0
    
    def cleanup(self):
        """Cleanup resources"""
        # MPU6050 doesn't need special cleanup
        pass


def run_gsg_loop(gsg_instance, interval, callback, stop_event):
    """
    Main loop for GSG sensor.
    
    Args:
        gsg_instance: GSG instance
        interval: Reading interval in seconds
        callback: Callback function to call with movement status (0 or 1)
        stop_event: Threading event to stop the loop
    """
    while not stop_event.is_set():
        try:
            movement = gsg_instance.detect_movement()
            callback(movement)
            time.sleep(interval)
        except Exception as e:
            print(f"[GSG] Error in sensor loop: {e}")
            time.sleep(1)
    
    # Cleanup on exit
    try:
        gsg_instance.cleanup()
    except Exception:
        pass
