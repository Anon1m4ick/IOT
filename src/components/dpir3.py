import threading
import time
from settings import load_settings

from simulators.dpir3 import run_dpir3_simulator

def dpir3_callback(message):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Message: {message}")

def run_dpir3(settings, threads, stop_event, callback=None, mqtt_publisher=None):
    if callback is None:
        callback = dpir3_callback
    
    def enhanced_callback(message):
        callback(message)
        if mqtt_publisher:
            value = 1 if "detected" in str(message).lower() else 0
            mqtt_publisher.add_sensor_data("DPIR3", value, settings['simulated'])
    
    if settings['simulated']:
        print("Starting dpir3 simulator")
        dpir3_thread = threading.Thread(target=run_dpir3_simulator, args=(enhanced_callback, stop_event))
        dpir3_thread.start()
        threads.append(dpir3_thread)
        print("Dpir3 simulator started")
    else:
        print("Error: Real hardware implementation for DPIR3 is not available. Please use simulated mode.")
