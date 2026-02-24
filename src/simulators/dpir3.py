import time
import random

def generate_values(initial_value=0):
    state = initial_value
    while True:
        time.sleep(random.uniform(0.5, 3))
        if random.random() < 0.5:
            state = 1 - state
        yield state

def run_dpir3_simulator(callback, stop_event):
    previous_state = None
    for dpir3_state in generate_values():
        if previous_state is not None and previous_state == 0 and dpir3_state == 1:
            callback("Motion detected")
        previous_state = dpir3_state
        if stop_event.is_set():
            break
