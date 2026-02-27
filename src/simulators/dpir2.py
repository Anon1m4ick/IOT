import time
import random


def generate_values(initial_value=0):
    """Fewer motion events: longer pauses, lower probability of 0->1."""
    state = initial_value
    while True:
        time.sleep(random.uniform(2.0, 5.0))
        if random.random() < 0.18:
            state = 1 - state
        yield state

def run_dpir2_simulator(callback, stop_event):
    previous_state = None
    for dpir2_state in generate_values():
        if previous_state is not None and previous_state == 0 and dpir2_state == 1:
            callback("Motion detected")
        previous_state = dpir2_state
        if stop_event.is_set():
            break
