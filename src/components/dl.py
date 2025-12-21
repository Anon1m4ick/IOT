import threading
import time
from typing import Dict
from simulators.dl import set_dl_state, get_dl_state

def run_dl(config: Dict):
    if config["simulated"]:
        return {
            "set_state": lambda state: set_dl_state(state),
            "get_state": get_dl_state,
            "simulated": True
        }
    else:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(config['pin'], GPIO.OUT)
        
        def set_state(state: int):
            GPIO.output(config['pin'], GPIO.HIGH if state else GPIO.LOW)
            return state
        
        def get_state():
            return GPIO.input(config['pin'])
        
        return {
            "set_state": set_state,
            "get_state": get_state,
            "simulated": False
        }

