"""Actual host measurements. Unavailable GPU sensors are null, never simulated."""

import asyncio
import shutil
import time
from pathlib import Path

import psutil

from jarvis.processes import run_process


class Telemetry:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.started = time.monotonic()
        self.cached: dict = {}
        self.measured = 0.0
        self.lock = asyncio.Lock()
        psutil.cpu_percent()

    async def sample(self) -> dict:
        async with self.lock:
            if self.cached and time.monotonic() - self.measured < 2:
                return self.cached
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(str(self.workspace))
            network = psutil.net_io_counters()
            gpu: list[dict] | None = None
            if shutil.which("nvidia-smi"):
                try:
                    output = await run_process(
                        [
                            "nvidia-smi",
                            "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                            "--format=csv,noheader,nounits",
                        ],
                        self.workspace,
                        timeout=3,
                    )
                    if output["exit_code"] == 0:
                        gpu = []
                        for line in output["output"].splitlines():
                            name, usage, used, total = line.rsplit(",", 3)
                            gpu.append(
                                {
                                    "name": name,
                                    "percent": float(usage),
                                    "used_mib": float(used),
                                    "total_mib": float(total),
                                }
                            )
                except (ValueError, OSError, TimeoutError):
                    gpu = None
            self.cached = {
                "cpu_percent": psutil.cpu_percent(),
                "ram_percent": memory.percent,
                "ram_used": memory.used,
                "ram_total": memory.total,
                "disk_percent": disk.percent,
                "disk_free": disk.free,
                "network_sent": network.bytes_sent,
                "network_received": network.bytes_recv,
                "process_count": len(psutil.pids()),
                "host_uptime": time.time() - psutil.boot_time(),
                "app_uptime": time.monotonic() - self.started,
                "gpu": gpu,
                "measured_at": time.time(),
            }
            self.measured = time.monotonic()
            return self.cached
