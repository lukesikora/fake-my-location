"""Holds one location-simulation session open with the iPhone.

Spawned by server.py. Reads JSON commands on stdin, one per line:
    {"cmd": "set", "lat": 40.0, "lon": -74.0}
    {"cmd": "clear"}
Writes JSON events on stdout, one per line:
    {"event": "ready"} | {"event": "ok", "cmd": ...} | {"event": "error", "message": ...}

The simulated location lasts only while this process keeps the session open,
so the server keeps it running for as long as you are spoofing.
"""

import asyncio
import json
import sys

from typer_injector import InjectingTyper

from pymobiledevice3.cli.cli_common import ServiceProviderDep, async_command
from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation

app = InjectingTyper(add_completion=False)


def emit(**event) -> None:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


@app.command()
@async_command
async def run(service_provider: ServiceProviderDep) -> None:
    async with DvtProvider(service_provider) as dvt, LocationSimulation(dvt) as sim:
        emit(event="ready")

        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)

        while True:
            line = await reader.readline()
            if not line:  # server went away
                break
            try:
                msg = json.loads(line)
                if msg["cmd"] == "set":
                    await sim.set(float(msg["lat"]), float(msg["lon"]))
                elif msg["cmd"] == "clear":
                    await sim.clear()
                else:
                    raise ValueError(f"unknown command {msg['cmd']!r}")
                emit(event="ok", cmd=msg["cmd"])
            except Exception as e:  # report and keep the session alive
                emit(event="error", message=str(e))

        try:
            await sim.clear()
        except Exception:
            pass


if __name__ == "__main__":
    app()
