from typing import Dict
from simulators.db import activate_db

def run_db(config: Dict):
    if config["simulated"]:
        return {
            "activate": lambda freq, dur: activate_db(freq, dur),
            "simulated": True
        }
    else:
        pass
