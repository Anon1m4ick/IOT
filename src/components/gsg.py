"""
GSG component - Gyroscope sensor for motion detection
Returns 0 (no movement) or 1 (significant movement detected)
"""
import threading
from simulators.gsg import run_gsg_simulator


def gsg_callback(message):
    """Default callback for GSG updates"""
    status = "Movement detected" if message == 1 else "No movement"
    print(f"GSG: {status} ({message})")


def run_gsg(settings, threads, stop_event, callback=None, mqtt_publisher=None, simulator_scheduler=None):
    """
    Run GSG component.
    
    Args:
        settings: GSG settings from settings.json
        threads: List to append thread to
        stop_event: Event to stop the thread
        callback: Optional callback for sensor updates
        mqtt_publisher: Optional MQTT publisher
    """
    if callback is None:
        callback = gsg_callback
    
    interval = settings.get('interval', 0.5)  # Default 0.5 seconds
    
    # Track previous state to send only on change
    previous_state = [None]  # Use list to allow modification in nested function
    
    def enhanced_callback(value):
        """Enhanced callback that sends to MQTT only when state changes"""
        callback(value)
        # Send to MQTT only when state changes (0→1 or 1→0)
        if mqtt_publisher and value != previous_state[0]:
            mqtt_publisher.add_sensor_data("GSG", value, settings['simulated'])
            previous_state[0] = value
    
    if settings['simulated']:
        print("Starting GSG simulator")
        gsg_thread = threading.Thread(
            target=run_gsg_simulator,
            args=(interval, enhanced_callback, stop_event, simulator_scheduler)
        )
        gsg_thread.start()
        threads.append(gsg_thread)
        print("GSG simulator started")
    else:
        from sensors.gsg import run_gsg_loop, GSG
        print("Starting GSG real hardware")
        threshold = settings.get('threshold', 2000)  # Movement threshold
        calibration_samples = settings.get('calibration_samples', 10)
        gsg = GSG(threshold=threshold, calibration_samples=calibration_samples)
        gsg_thread = threading.Thread(
            target=run_gsg_loop,
            args=(gsg, interval, enhanced_callback, stop_event)
        )
        gsg_thread.start()
        threads.append(gsg_thread)
        print("GSG real hardware started")
