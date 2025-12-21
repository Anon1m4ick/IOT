import threading
import time

from settings import load_settings
from simulators.dus1 import run_dus1_simulator

def dus1_callback(message):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Dust distance: {message}")

def run_dus1(settings, threads, stop_event, callback=None):
    if callback is None:
        callback = dus1_callback
    
    if settings['simulated']:
        print("Starting dus1 simulator")
        dus1_thread = threading.Thread(target=run_dus1_simulator, args=(callback, stop_event))
        dus1_thread.start()
        threads.append(dus1_thread)
        print("Dus1 simulator started")
    else:
        from sensors.dus1 import run_dus1_loop, DUS1
        print("Starting dus1 loop")
        dus1 = DUS1(settings['pin'])
        dus1_thread = threading.Thread(target=run_dus1_loop, args=(dus1, 0.5, callback, stop_event))
        dus1_thread.start()
        threads.append(dus1_thread)
        print("Dus1 loop started")

# settings = load_settings()
# ds1_settings = settings['DS1']
# threads = []
# stop_event = threading.Event()
# run_dus1(ds1_settings, threads, stop_event)