import time
import random


def generate_values(initial_value=0):
    """Rare motion events to avoid constant alarm activations in simulation."""
    state = initial_value
    while True:
        time.sleep(random.uniform(6.0, 14.0))
        if random.random() < 0.08:
            state = 1 - state
        yield state

# def run_dpir1_simulator(callback, stop_event):
#     for dpir1_state in generate_values():
#         if dpir1_state == 1:
#             callback("Motion detected")
#         if stop_event.is_set():
#             break

def run_dpir1_simulator(callback, stop_event):
    previous_state = None
    for dpir1_state in generate_values():
        if previous_state is not None and previous_state == 0 and dpir1_state == 1:
            callback("Motion detected")
        previous_state = dpir1_state
        if stop_event.is_set():
            break
