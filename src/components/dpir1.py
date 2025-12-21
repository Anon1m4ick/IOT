import threading
import time
from settings import load_settings


from simulators.dpir1 import run_dpir1_simulator

def dpir1_callback(message):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Message: {message}")

def run_dpir1(settings, threads, stop_event, callback=None):
    if callback is None:
        callback = dpir1_callback
    
    if settings['simulated']:
        print("Starting dpir1 simulator")
        dpir1_thread = threading.Thread(target=run_dpir1_simulator, args=(callback, stop_event))
        dpir1_thread.start()
        threads.append(dpir1_thread)
        print("Dpir1 simulator started")
    else:
        from sensors.dpir1 import run_dpir1_loop, DPIR1
        print("Starting dpir1 loop")
        dpir1 = DPIR1(settings['pin'])
        dpir1_thread = threading.Thread(target=run_dpir1_loop, args=(dpir1, 0.5, callback, stop_event))
        dpir1_thread.start()
        threads.append(dpir1_thread)
        print("Dpir1 loop started")

# settings = load_settings()
# dpir1_settings = settings['DPIR1']
# threads = []
# stop_event = threading.Event()
# run_dpir1(dpir1_settings, threads, stop_event)