import time
import random

def generate_values(initial_value=""):
    pin_buttons = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#']
    control_buttons = ['A', 'B', 'C', 'D']
    while True:
        time.sleep(random.uniform(5.0, 15.0))
        if random.random() < 0.08:
            if random.random() < 0.95:
                value = random.choice(pin_buttons)
            else:
                value = random.choice(control_buttons)
            yield value
        else:
            yield None

def run_dms_simulator(callback, stop_event, simulator_scheduler=None):
    if simulator_scheduler:
        slot_count = 0
        while not stop_event.is_set():
            if not simulator_scheduler.wait_for_turn("DMS"):
                break
            slot_count += 1
            if slot_count % 30 == 0:
                callback("Button pressed: *")
        return

    for button in generate_values():
        if button is not None:
            callback(f"Button pressed: {button}")
        if stop_event.is_set():
            break

