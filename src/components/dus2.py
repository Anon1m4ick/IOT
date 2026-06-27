import threading
import time

from simulators.dus2 import run_dus2_simulator

def dus2_callback(message):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Dust distance: {message}")

def run_dus2(settings, threads, stop_event, callback=None, mqtt_publisher=None, simulator_scheduler=None):
    if callback is None:
        callback = dus2_callback
    
    def enhanced_callback(message):
        callback(message)
        if mqtt_publisher:
            value = message if isinstance(message, (int, float)) else int(message) if str(message).isdigit() else 0
            mqtt_publisher.add_sensor_data("DUS2", value, settings['simulated'])
    
    if settings['simulated']:
        print("Starting dus2 simulator")
        dus2_thread = threading.Thread(target=run_dus2_simulator, args=(enhanced_callback, stop_event, simulator_scheduler))
        dus2_thread.start()
        threads.append(dus2_thread)
        print("Dus2 simulator started")
    else:
        from sensors.dus2 import run_dus2_loop, DUS2
        print("Starting dus2 loop")
        dus2 = DUS2(settings['trig_pin'], settings['echo_pin'])
        dus2_thread = threading.Thread(target=run_dus2_loop, args=(dus2, 0.5, enhanced_callback, stop_event))
        dus2_thread.start()
        threads.append(dus2_thread)
        print("Dus2 loop started")
