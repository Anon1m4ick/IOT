import threading
import time
from settings import load_settings

from simulators.ds1 import run_ds1_simulator

def ds1_callback(message):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Message: {message}")

def run_ds1(settings, threads, stop_event):
    if settings['simulated']:
        print("Starting ds1 simulator")
        ds1_thread = threading.Thread(target=run_ds1_simulator, args=(0.5, ds1_callback, stop_event))
        ds1_thread.start()
        threads.append(ds1_thread)
        print("Ds1 simulator started")
    else:
        from sensors.ds1 import run_ds1_loop, DS1
        print("Starting ds1 loop")
        ds1 = DS1(settings['pin'])
        ds1_thread = threading.Thread(target=run_ds1_loop, args=(ds1, 0.5, ds1_callback, stop_event))
        ds1_thread.start()
        threads.append(ds1_thread)
        print("Ds1 loop started")

# settings = load_settings()
# ds1_settings = settings['DS1']
# threads = []
# stop_event = threading.Event()
# run_ds1(ds1_settings, threads, stop_event)