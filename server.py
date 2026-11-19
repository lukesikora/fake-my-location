"""Fake My Location: a local web app that moves your iPhone's GPS location.

Run with ./start.sh. Open the printed link on your Mac or iPhone (same Wi-Fi).
"""

import asyncio
import json
import math
import os
import secrets
import socket
import sys
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
TOKEN_FILE = DATA / "token.txt"
FAVORITES_FILE = DATA / "favorites.json"


def free_port(start: int) -> int:
    """First port from `start` up that nothing else is listening on."""
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise SystemExit(f"No free port found between {start} and {start + 49}.")


PORT = int(os.getenv("PORT") or free_port(8765))

if TOKEN_FILE.exists():
    TOKEN = TOKEN_FILE.read_text().strip()
else:
    TOKEN = secrets.token_urlsafe(9)
    TOKEN_FILE.write_text(TOKEN)


# ---------------------------------------------------------------- geo helpers

EARTH_M = 6_371_000


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_M * math.asin(math.sqrt(h))


def lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    # Fine for the short hops between route points.
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


# ---------------------------------------------------------------- device session


class Session:
    """Owns the worker process that keeps the location simulation alive."""

    def __init__(self) -> None:
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.udid: Optional[str] = None
        self.events: asyncio.Queue = asyncio.Queue()
        self.stderr_tail: deque[str] = deque(maxlen=40)
        self.lock = asyncio.Lock()
        self.position: Optional[tuple[float, float]] = None
        self.walk_task: Optional[asyncio.Task] = None
        self.walk_target: Optional[tuple[float, float]] = None
        self.walk_route: list[tuple[float, float]] = []
        self.walk_remaining_m: float = 0
        self.walk_speed_kmh: float = 0
        self.label: Optional[str] = None
        self.status = "idle"  # idle | connecting | active | walking | error
        self.error: Optional[str] = None

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def _pump_stdout(self, proc) -> None:
        async for line in proc.stdout:
            try:
                await self.events.put(json.loads(line))
            except json.JSONDecodeError:
                self.stderr_tail.append(line.decode(errors="replace").rstrip())
        await self.events.put({"event": "exit"})

    async def _pump_stderr(self, proc) -> None:
        async for line in proc.stderr:
            self.stderr_tail.append(line.decode(errors="replace").rstrip())

    def _explain_failure(self) -> str:
        """Turn the worker's error output into a plain-English next step."""
        tail = "\n".join(self.stderr_tail)
        if "NoDeviceConnected" in tail or "DeviceNotFound" in tail or "No device" in tail:
            return ("iPhone not found. Plug it into this Mac with a cable and unlock it. "
                    "If it still doesn't show up, try a different cable (some only charge).")
        if "UserDeniedPairing" in tail:
            return "The iPhone said Don't Trust. Unplug it, plug it back in, unlock it and tap Trust."
        if "PasswordRequired" in tail or "PasswordProtected" in tail:
            return "Unlock your iPhone, then try again."
        if "PairingDialog" in tail or "NotPaired" in tail or "pair" in tail.lower():
            return "Look at your iPhone: tap Trust and enter your passcode, then try again."
        if "DeveloperMode" in tail or "Developer Mode" in tail or "InvalidService" in tail:
            self._reveal_developer_mode()
            return ("Developer Mode is off. On your iPhone open Settings > Privacy & Security > Developer Mode "
                    "(scroll to the bottom), turn it on and let the phone restart. After it restarts, unlock it, "
                    "tap Turn On, then try again.")
        last = [l for l in self.stderr_tail if l.strip()]
        return "Could not connect to the iPhone: " + (last[-1] if last else "unknown error")

    def _reveal_developer_mode(self) -> None:
        """Make the Developer Mode switch appear in iPhone Settings (it is hidden until a Mac asks for it)."""
        args = [sys.executable, "-m", "pymobiledevice3", "amfi", "reveal-developer-mode"]
        if self.udid:
            args += ["--udid", self.udid]
        asyncio.get_running_loop().create_task(
            asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        )

    async def _start(self) -> None:
        self.status, self.error = "connecting", None
        self.stderr_tail.clear()
        self.events = asyncio.Queue()
        udid = self.udid or await pick_device()
        self.udid = udid
        args = [sys.executable, str(ROOT / "worker.py"), "--userspace"]
        if udid:
            args += ["--udid", udid]
        self.proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        asyncio.create_task(self._pump_stdout(self.proc))
        asyncio.create_task(self._pump_stderr(self.proc))
        try:
            ev = await asyncio.wait_for(self.events.get(), timeout=60)
        except asyncio.TimeoutError:
            ev = {"event": "timeout"}
        if ev.get("event") != "ready":
            await self._kill()
            self.status = "error"
            self.error = (
                "Timed out connecting to the iPhone. Make sure it is unlocked."
                if ev.get("event") == "timeout"
                else self._explain_failure()
            )
            raise HTTPException(503, self.error)

    async def _kill(self) -> None:
        if self.alive:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), 5)
            except asyncio.TimeoutError:
                self.proc.kill()
        self.proc = None

    async def _send(self, msg: dict) -> None:
        if not self.alive:
            await self._start()
        self.proc.stdin.write((json.dumps(msg) + "\n").encode())
        await self.proc.stdin.drain()
        ev = await asyncio.wait_for(self.events.get(), timeout=20)
        if ev.get("event") == "exit":
            self.proc = None
            self.status, self.error = "error", self._explain_failure()
            raise HTTPException(503, self.error)
        if ev.get("event") == "error":
            raise HTTPException(500, ev.get("message", "unknown error"))

    async def set(self, lat: float, lon: float) -> None:
        async with self.lock:
            await self._send({"cmd": "set", "lat": lat, "lon": lon})
            self.position = (lat, lon)
            if self.status != "walking":
                self.status = "active"

    async def clear(self) -> None:
        self.stop_walk()
        async with self.lock:
            if self.alive:
                try:
                    await self._send({"cmd": "clear"})
                except HTTPException:
                    pass
            await self._kill()
            self.position = None
            self.label = None
            self.status, self.error = "idle", None

    def stop_walk(self) -> None:
        if self.walk_task and not self.walk_task.done():
            self.walk_task.cancel()
        self.walk_task = None
        self.walk_target = None
        self.walk_route = []
        self.walk_remaining_m = 0
        if self.status == "walking":
            self.status = "active"

    def start_walk(self, route: list[tuple[float, float]], speed_kmh: float) -> None:
        self.stop_walk()
        self.walk_target = route[-1]
        self.walk_route = route
        self.walk_speed_kmh = speed_kmh
        self.walk_task = asyncio.create_task(self._walk(route, speed_kmh))

    async def _walk(self, route: list[tuple[float, float]], speed_kmh: float) -> None:
        step_m = speed_kmh / 3.6  # metres per 1-second tick
        self.status = "walking"
        try:
            here = route[0]
            await self.set(*here)
            # metres left after each leg's end point
            after = [0.0] * len(route)
            for i in range(len(route) - 2, -1, -1):
                after[i] = after[i + 1] + distance_m(route[i], route[i + 1])
            for i, target in enumerate(route[1:], start=1):
                while True:
                    remaining = distance_m(here, target)
                    self.walk_remaining_m = remaining + after[i]
                    if remaining <= step_m:
                        here = target
                        await self.set(*here)
                        await asyncio.sleep(remaining / step_m if step_m else 1)
                        break
                    here = lerp(here, target, step_m / remaining)
                    await self.set(*here)
                    await asyncio.sleep(1)
        except HTTPException:
            pass
        finally:
            self.walk_target = None
            self.walk_route = []
            self.walk_remaining_m = 0
            if self.status == "walking":
                self.status = "active"


session = Session()


async def list_devices() -> list[dict]:
    from pymobiledevice3 import usbmux
    from pymobiledevice3.lockdown import create_using_usbmux

    out = []
    try:
        devices = await usbmux.list_devices()
    except Exception:
        return out
    for d in devices:
        info = {"udid": d.serial, "connection": "USB" if d.is_usb else "Wi-Fi", "name": None, "ios": None}
        try:
            ld = await asyncio.wait_for(
                create_using_usbmux(d.serial, autopair=False, connection_type=d.connection_type), 5
            )
            info["name"] = ld.all_values.get("DeviceName")
            info["ios"] = ld.product_version
            await ld.close()
        except Exception:
            pass
        out.append(info)
    # one entry per phone, preferring USB
    seen: dict[str, dict] = {}
    for d in out:
        if d["udid"] not in seen or d["connection"] == "USB":
            seen[d["udid"]] = d
    return list(seen.values())


async def pick_device() -> Optional[str]:
    devices = await list_devices()
    return devices[0]["udid"] if devices else None


# ---------------------------------------------------------------- web app

@asynccontextmanager
async def lifespan(_app):
    yield
    await session.clear()  # restore the real location when the server stops


app = FastAPI(title="Fake My Location", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.middleware("http")
async def require_token(request: Request, call_next):
    """Anyone on your Wi-Fi could otherwise move your phone. The link carries a secret."""
    t = request.query_params.get("t")
    if t == TOKEN:
        if request.url.path == "/":
            resp = RedirectResponse("/")
            resp.set_cookie("fml", TOKEN, max_age=60 * 60 * 24 * 365, httponly=True, samesite="strict")
            return resp
    elif request.cookies.get("fml") != TOKEN:
        return JSONResponse({"detail": "Open the full link printed in the terminal."}, status_code=401)
    return await call_next(request)


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    label: Optional[str] = Field(default=None, max_length=120)


class WalkReq(BaseModel):
    to: Point
    speed_kmh: float = Field(default=5, gt=0, le=300)
    roads: bool = True


class Favorite(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    lat: float
    lon: float


def load_favorites() -> list[dict]:
    try:
        return json.loads(FAVORITES_FILE.read_text())
    except Exception:
        return []


@app.get("/")
async def index():
    return FileResponse(ROOT / "static" / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse(ROOT / "static" / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/icon.png")
async def icon():
    return FileResponse(ROOT / "static" / "icon.png")


@app.get("/api/status")
async def status():
    return {
        "status": session.status,
        "error": session.error,
        "position": session.position,
        "walk_target": session.walk_target,
        "walk_route": session.walk_route,
        "walk_remaining_m": round(session.walk_remaining_m),
        "walk_speed_kmh": session.walk_speed_kmh,
        "label": session.label,
        "connected": session.alive,
    }


@app.get("/api/devices")
async def devices():
    return await list_devices()


@app.post("/api/set")
async def set_location(p: Point):
    session.stop_walk()
    await session.set(p.lat, p.lon)
    session.label = p.label
    return await status()


@app.post("/api/walk")
async def walk(req: WalkReq):
    if session.position is None:
        raise HTTPException(400, "Set a starting location first, then walk from there.")
    start = session.position
    end = (req.to.lat, req.to.lon)
    route = [start, end]
    if req.roads:
        road = await road_route(start, end, req.speed_kmh)
        if road:
            route = [start, *road, end]  # OSRM snaps ends to the nearest road
    session.start_walk(route, req.speed_kmh)
    session.label = req.to.label
    return {"route": route}


@app.post("/api/stop")
async def stop():
    session.stop_walk()
    session.label = None  # stopped partway, so the destination name no longer applies
    return await status()


@app.post("/api/clear")
async def clear():
    await session.clear()
    return await status()


@app.get("/api/favorites")
async def favorites():
    return load_favorites()


@app.post("/api/favorites")
async def add_favorite(f: Favorite):
    favs = [x for x in load_favorites() if x["name"] != f.name] + [f.model_dump()]
    FAVORITES_FILE.write_text(json.dumps(favs, indent=2))
    return favs


@app.delete("/api/favorites/{name}")
async def delete_favorite(name: str):
    favs = [x for x in load_favorites() if x["name"] != name]
    FAVORITES_FILE.write_text(json.dumps(favs, indent=2))
    return favs


async def road_route(a, b, speed_kmh: float) -> Optional[list[tuple[float, float]]]:
    """Follow real streets using the public OSRM demo server; None if unavailable."""
    import httpx

    profile = "foot" if speed_kmh <= 8 else "bike" if speed_kmh <= 25 else "driving"
    url = (
        f"https://router.project-osrm.org/route/v1/{profile}/"
        f"{a[1]},{a[0]};{b[1]},{b[0]}?overview=full&geometries=geojson"
    )
    try:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "fake-my-location/1.0"}) as c:
            r = await c.get(url)
            r.raise_for_status()
            coords = r.json()["routes"][0]["geometry"]["coordinates"]
            return [(lat, lon) for lon, lat in coords]
    except Exception:
        return None


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def banner() -> None:
    ip = lan_ip()
    local = f"http://localhost:{PORT}/?t={TOKEN}"
    phone = f"http://{ip}:{PORT}/?t={TOKEN}"
    print("\n  FML · Fake My Location is running\n")
    print(f"  On this Mac:   {local}")
    print(f"  On your phone: {phone}\n")
    try:
        import qrcode

        qr = qrcode.QRCode(border=1)
        qr.add_data(phone)
        qr.print_ascii(invert=True)
        print("  Scan with your iPhone camera, then Share > Add to Home Screen.\n")
    except Exception:
        pass
    print("  Keep this window open while spoofing. Ctrl+C stops and restores your real location.\n")


if __name__ == "__main__":
    banner()
    if "--open" in sys.argv:
        os.system(f"open 'http://localhost:{PORT}/?t={TOKEN}'")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
