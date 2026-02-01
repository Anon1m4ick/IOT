import time
import random

def generate_values(initial_value=25):
    value = initial_value
    while True:
        time.sleep(random.uniform(0.5, 3))
        value = random.randint(1, 50)
        yield value

# def run_dus1_simulator(callback, stop_event):
#     for dust_value in generate_values():
#         callback(dust_value)
#         if stop_event.is_set():
#             break

import time
import random

def run_dus1_simulator(callback, stop_event):
    MIN_DISTANCE = 0 
    MAX_DISTANCE = 50  
    current_distance = MIN_DISTANCE
    is_opening = True  
    
    while not stop_event.is_set():
        step = random.uniform(3.0, 7.0)
        
        sleep_time = random.uniform(1.0, 2.0)
        
        if is_opening:
            
            current_distance += step
            if current_distance >= MAX_DISTANCE:
                current_distance = MAX_DISTANCE
                callback("Door opened")
                is_opening = False 
        else:
            
            current_distance -= step
            if current_distance <= MIN_DISTANCE:
                current_distance = MIN_DISTANCE
                callback("Door closed")
                is_opening = True  
        
        callback(int(current_distance))
        
        time.sleep(sleep_time)