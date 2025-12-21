import json
from typing import Dict

def load_settings(filePath: str = 'settings.json') -> Dict:
    with open(filePath, 'r') as f:
        return json.load(f)
