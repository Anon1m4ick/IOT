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
       pass
