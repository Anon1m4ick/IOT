import threading
import time
from settings import load_settings
from simulators.dms import run_dms_simulator

def dms_callback(message):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Message: {message}")

def run_dms(settings, threads, stop_event):
    if settings['simulated']:
        print("Starting dms simulator")
        dms_thread = threading.Thread(target=run_dms_simulator, args=(dms_callback, stop_event))
        dms_thread.start()
        threads.append(dms_thread)
        print("Dms simulator started")
    else:
        from sensors.dms import run_dms_loop, DMS
        print("Starting dms loop")
        dms = DMS(settings['rows'], settings['cols'])
        dms_thread = threading.Thread(target=run_dms_loop, args=(dms, 0.5, dms_callback, stop_event))
        dms_thread.start()
        threads.append(dms_thread)
        print("Dms loop started")

