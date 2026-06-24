"""
Minimal smbus compatibility module for Docker runs without I2C hardware.
"""
from __future__ import annotations

import os
from collections import defaultdict

_log_counts: defaultdict[str, int] = defaultdict(int)
_verbose = os.getenv("SMBUS_COMPAT_VERBOSE", "").lower() in {"1", "true", "yes", "on"}
_log_reads = os.getenv("SMBUS_COMPAT_LOG_READS", "").lower() in {"1", "true", "yes", "on"}


def _log(action: str, detail: str, limit: int = 12) -> None:
    _log_counts[action] += 1
    count = _log_counts[action]
    if not _verbose and count > limit:
        return
    suffix = "" if count <= limit else f" (call {count})"
    print(f"[SMBUS-COMPAT] {action}: {detail}{suffix}", flush=True)


class SMBus:
    def __init__(self, bus: int):
        self.bus = int(bus)
        self._registers: dict[tuple[int, int], int] = {}
        _log("SMBus.__init__", f"bus={self.bus}")

    def write_byte(self, address: int, value: int) -> None:
        _log("write_byte", f"bus={self.bus} address=0x{address:02x} value=0x{value & 0xff:02x}")

    def read_byte_data(self, address: int, register: int) -> int:
        value = self._registers.get((address, register), 0)
        if _verbose or _log_reads:
            _log("read_byte_data", f"bus={self.bus} address=0x{address:02x} register=0x{register:02x} -> 0x{value:02x}")
        return value

    def write_byte_data(self, address: int, register: int, value: int) -> None:
        self._registers[(address, register)] = value & 0xff
        _log("write_byte_data", f"bus={self.bus} address=0x{address:02x} register=0x{register:02x} value=0x{value & 0xff:02x}")

    def read_i2c_block_data(self, address: int, register: int, length: int) -> list[int]:
        data = [0] * int(length)
        if _verbose or _log_reads:
            _log("read_i2c_block_data", f"bus={self.bus} address=0x{address:02x} register=0x{register:02x} length={length} -> {data}")
        return data
