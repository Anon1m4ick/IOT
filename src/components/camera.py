"""
USB camera module wrapper for MJPG streamer.
Provides optional process control and stream URL access for runtime/web layers.
"""
import subprocess
import threading
import shutil
from typing import Dict, Optional


class CameraController:
    def __init__(self, settings: Dict, callback=None):
        self.settings = settings or {}
        self.callback = callback or (lambda msg: print(f"CAMERA: {msg}"))
        # Camera is real-only in this project; simulation is not supported.
        self.simulated = False
        if bool(self.settings.get("simulated", False)):
            self.callback("CAMERA simulation is not supported; forcing real mode")
        self.port = int(self.settings.get("port", 8080))
        self.stream_url = str(
            self.settings.get("stream_url", f"http://localhost:{self.port}/?action=stream")
        )
        self.auto_start = bool(self.settings.get("auto_start", False))
        self.command = str(
            self.settings.get(
                "mjpg_command",
                f'mjpg_streamer -i "input_uvc.so" -o "output_http.so -p {self.port} -w /usr/local/share/mjpg-streamer/www"',
            )
        )

        self._lock = threading.Lock()
        self._process: Optional[subprocess.Popen] = None

        if self.auto_start:
            self.start()

    def start(self) -> bool:
        with self._lock:
            if self._process and self._process.poll() is None:
                self.callback("Camera streamer already running")
                return True
            if shutil.which("mjpg_streamer") is None:
                self.callback("mjpg_streamer not found in PATH")
                return False
            try:
                self._process = subprocess.Popen(
                    self.command,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.callback("Camera streamer started")
                return True
            except Exception as exc:
                self.callback(f"Failed to start camera streamer: {exc}")
                self._process = None
                return False

    def stop(self) -> bool:
        with self._lock:
            if not self._process or self._process.poll() is not None:
                self._process = None
                self.callback("Camera streamer is not running")
                return True
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            finally:
                self._process = None
            self.callback("Camera streamer stopped")
            return True

    def cleanup(self):
        self.stop()

    def get_state(self) -> Dict:
        with self._lock:
            running = bool(self._process and self._process.poll() is None)
            return {
                "simulated": self.simulated,
                "running": running,
                "stream_url": self.stream_url,
                "port": self.port,
                "auto_start": self.auto_start,
            }


def run_camera(settings: Dict, threads, stop_event, callback=None):
    controller = CameraController(settings, callback=callback)

    def cleanup_worker():
        stop_event.wait()
        controller.cleanup()

    worker = threading.Thread(target=cleanup_worker, daemon=True)
    worker.start()
    threads.append(worker)

    return {
        "start": controller.start,
        "stop": controller.stop,
        "get_state": controller.get_state,
        "simulated": controller.simulated,
    }
