import time

def run_dl_simulator(callback, stop_event):
    while not stop_event.is_set():
        time.sleep(0.1)
    callback("LED Simulator stopped")

def set_dl_state(state: int):
    global _dl_state
    _dl_state = state
    return state

def get_dl_state():
    global _dl_state
    try:
        return _dl_state
    except NameError:
        _dl_state = 0
        return 0

_dl_state = 0
