"""
Simulator for IR (Infrared Receiver) sensor
Simulates IR remote control commands
"""
import time
import random


def run_ir_simulator(callback, stop_event):
    """
    Simulate IR sensor by generating random button presses.
    
    Args:
        callback: Callback function to call with button name
        stop_event: Threading event to stop the loop
    """
    buttons = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "OK", "UP", "DOWN", "LEFT", "RIGHT", "*", "#"]
    
    while not stop_event.is_set():
        try:
            # Randomly generate button press (with higher probability for digits 1-9)
            if random.random() < 0.7:  # 70% chance of digit button
                button = random.choice(["1", "2", "3", "4", "5", "6", "7", "8", "9"])
            else:  # 30% chance of other buttons
                button = random.choice(buttons)
            
            callback(button)
            time.sleep(random.uniform(2.0, 5.0))  # Wait 2-5 seconds between button presses
        except Exception as e:
            print(f"[IR Simulator] Error: {e}")
            time.sleep(1)
