import time
import random

def run_dus2_simulator(callback, stop_event):
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
