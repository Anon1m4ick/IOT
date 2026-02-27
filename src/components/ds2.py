import threading
import time

from settings import load_settings
from simulators.ds2 import run_ds2_simulator

def ds2_callback(message):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Message: {message}")

def run_ds2(settings, threads, stop_event, callback=None, mqtt_publisher=None):
    if callback is None:
        callback = ds2_callback

    def enhanced_callback(message):
        callback(message)
        if mqtt_publisher:
            value = 1 if "Pressed" in str(message) else 0
            mqtt_publisher.add_sensor_data("DS2", value, settings['simulated'])
    
    if settings['simulated']:
        print("Starting ds2 simulator")
        ds2_thread = threading.Thread(target=run_ds2_simulator, args=(enhanced_callback, stop_event))
        ds2_thread.start()
        threads.append(ds2_thread)
        print("Ds2 simulator started")
    else:
        from sensors.ds2 import run_ds2_loop, DS2
        print("Starting ds2 loop")
        ds2 = DS2(settings['pin'])
        ds2_thread = threading.Thread(target=run_ds2_loop, args=(ds2, 0.5, enhanced_callback, stop_event))
        ds2_thread.start()
        threads.append(ds2_thread)
        print("Ds2 loop started")
