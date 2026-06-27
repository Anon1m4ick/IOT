import threading
import time
from settings import load_settings

from simulators.dpir2 import run_dpir2_simulator

def dpir2_callback(message):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Message: {message}")

def run_dpir2(settings, threads, stop_event, callback=None, mqtt_publisher=None, simulator_scheduler=None):
    if callback is None:
        callback = dpir2_callback
    
    def enhanced_callback(message):
        callback(message)
        if mqtt_publisher:
            value = 1 if "detected" in str(message).lower() else 0
            mqtt_publisher.add_sensor_data("DPIR2", value, settings['simulated'])
    
    if settings['simulated']:
        print("Starting dpir2 simulator")
        dpir2_thread = threading.Thread(target=run_dpir2_simulator, args=(enhanced_callback, stop_event, simulator_scheduler))
        dpir2_thread.start()
        threads.append(dpir2_thread)
        print("Dpir2 simulator started")
    else:
        from sensors.dpir2 import run_dpir2_loop, DPIR2
        print("Starting dpir2 loop")
        dpir2 = DPIR2(settings['pin'])
        dpir2_thread = threading.Thread(target=run_dpir2_loop, args=(dpir2, 0.5, enhanced_callback, stop_event))
        dpir2_thread.start()
        threads.append(dpir2_thread)
        print("Dpir2 loop started")
