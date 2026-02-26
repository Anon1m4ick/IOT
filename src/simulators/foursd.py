import threading


class FourSegmentDisplaySimulator:
    """In-memory simulator for a 4-digit 7-segment display."""

    def __init__(self):
        self._lock = threading.Lock()
        self._text = "    "
        self._colon = False

    def show(self, text: str, colon: bool = True):
        with self._lock:
            self._text = (text or "    ")[:4].ljust(4)
            self._colon = bool(colon)

    def clear(self):
        self.show("    ", colon=False)

    def snapshot(self):
        with self._lock:
            return {"text": self._text, "colon": self._colon}

    def cleanup(self):
        return None
