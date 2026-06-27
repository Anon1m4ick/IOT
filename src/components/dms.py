import threading
import time
from simulators.dms import run_dms_simulator

def dms_callback(message):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Message: {message}")

def run_dms(settings, threads, stop_event, callback=None, mqtt_publisher=None, simulator_scheduler=None):
    if callback is None:
        callback = dms_callback

    
    def enhanced_callback(message):
        callback(message)
        if mqtt_publisher:
            value = str(message).replace("Button pressed: ", "") if "Button pressed:" in str(message) else str(message)
            mqtt_publisher.add_sensor_data("DMS", value, settings['simulated'])

    if settings['simulated']:
        print("Starting dms simulator")
        dms_thread = threading.Thread(target=run_dms_simulator, args=(enhanced_callback, stop_event, simulator_scheduler))
        dms_thread.start()
        threads.append(dms_thread)
        print("Dms simulator started")
    else:
        from sensors.dms import run_dms_loop, DMS
        print("Starting dms real hardware")
        rows = settings.get('rows', [25, 8, 7, 1])
        cols = settings.get('cols', [12, 16, 20, 21])
        dms = DMS(rows=rows, cols=cols)
        dms_thread = threading.Thread(target=run_dms_loop, args=(dms, 0.2, enhanced_callback, stop_event))
        dms_thread.start()
        threads.append(dms_thread)
        print("Dms real hardware started")
