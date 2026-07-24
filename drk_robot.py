"""drk_robot — a resilient connection layer for robot20 (and any Viam machine).

Why this exists
---------------
The machine is only reachable over Viam's WebRTC relay (direct gRPC is refused —
the robot is NAT'd). WebRTC is fine for small/occasional calls but drops the
stream on sustained large payloads — most reliably on repeated RealSense depth
pulls (~1.8 MB each). The stock `RobotClient` does not retry a call whose stream
was terminated, so one blip aborts your whole routine.

This wraps the SDK with:
  1. Tuned reconnect options (faster connection checks, more reconnect attempts).
  2. `call()` — runs any operation and, on a connection error, rebuilds the
     client and retries. Your dance / pick sequence survives a dropped stream.
  3. Payload-aware camera helpers: `get_color()` pulls color-only (small, stable)
     and is what a tracking loop should use; `get_color_and_depth()` pulls the
     heavy depth frame inside the retry wrapper for when you actually need 3D.

Credentials come from the environment, never hard-coded:
    VIAM_ADDR, VIAM_API_KEY, VIAM_API_KEY_ID

Usage
-----
    import asyncio
    from drk_robot import StableRobot

    async def main():
        async with StableRobot.from_env() as robot:
            arm = await robot.arm("arm-1")
            # any call, auto-retried through drops:
            jp = await robot.call(lambda: arm.get_joint_positions(), label="joints")
            imgs = await robot.get_color("cam-1")     # small, stable
            color, depth = await robot.get_color_and_depth("cam-1")  # retried

    asyncio.run(main())
"""
from __future__ import annotations

import asyncio
import io
import os
import struct
from typing import Awaitable, Callable, Optional, Tuple, TypeVar

from viam.robot.client import RobotClient
from viam.rpc.dial import DialOptions, Credentials
from viam.components.arm import Arm
from viam.components.gripper import Gripper
from viam.components.camera import Camera
from viam.services.vision import VisionClient

T = TypeVar("T")

# Errors that mean "the WebRTC stream died" rather than "your request was bad".
# We reconnect + retry on these; everything else propagates immediately.
_CONNECTION_ERRORS = (
    "StreamTerminatedError",
    "ConnectionClosedError",
    "Deadline exceeded",
    "Connection lost",
    "channel closed",
    "GOAWAY",
    "RpcError",
)


def _is_connection_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    text = f"{name}: {exc}"
    return any(tok in text for tok in _CONNECTION_ERRORS)


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from a sibling .env (gitignored), matching robot.py."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


class StableRobot:
    """A reconnecting wrapper around a Viam RobotClient."""

    def __init__(self, address: str, api_key: str, api_key_id: str,
                 *, max_call_retries: int = 4):
        self._address = address
        self._api_key = api_key
        self._api_key_id = api_key_id
        self._max_call_retries = max_call_retries
        self._machine: Optional[RobotClient] = None
        self._lock = asyncio.Lock()

    # ---- construction -------------------------------------------------------

    @classmethod
    def from_env(cls, **kwargs) -> "StableRobot":
        # Matches the repo's robot.py convention: load a gitignored .env, then
        # read VIAM_ADDRESS / VIAM_API_KEY / VIAM_API_KEY_ID from the environment.
        _load_dotenv()
        addr = os.environ.get("VIAM_ADDRESS") or os.environ.get("VIAM_ADDR")
        try:
            if not addr:
                raise KeyError("VIAM_ADDRESS")
            return cls(addr, os.environ["VIAM_API_KEY"],
                       os.environ["VIAM_API_KEY_ID"], **kwargs)
        except KeyError as e:
            raise RuntimeError(
                f"missing env var {e}; set VIAM_ADDRESS, VIAM_API_KEY, VIAM_API_KEY_ID "
                f"(in .env or the environment)"
            ) from None

    def _options(self) -> RobotClient.Options:
        # WebRTC is the only reachable transport for this machine, so we keep it
        # and make the client aggressive about noticing and healing drops.
        dial = DialOptions(
            credentials=Credentials(type="api-key", payload=self._api_key),
            auth_entity=self._api_key_id,
            disable_webrtc=False,       # direct gRPC is refused (NAT); must relay
            max_reconnect_attempts=7,   # default 3
            timeout=30,                 # default 20
        )
        return RobotClient.Options(
            refresh_interval=0,             # don't auto-poll every resource
            check_connection_interval=3,    # notice a dead link fast (default 10)
            attempt_reconnect_interval=1,   # and start healing immediately
            dial_options=dial,
        )

    async def connect(self) -> RobotClient:
        self._machine = await RobotClient.at_address(self._address, self._options())
        return self._machine

    async def _reconnect(self) -> None:
        async with self._lock:
            if self._machine is not None:
                try:
                    await self._machine.close()
                except Exception:
                    pass
                self._machine = None
            await self.connect()

    @property
    def machine(self) -> RobotClient:
        if self._machine is None:
            raise RuntimeError("not connected — use 'async with StableRobot...' or call connect()")
        return self._machine

    # ---- the core resilience primitive -------------------------------------

    async def call(self, op: Callable[[], Awaitable[T]], *,
                   label: str = "call", retries: Optional[int] = None) -> T:
        """Run `op()`; on a connection-class error, reconnect and retry.

        `op` is a zero-arg callable returning a coroutine, e.g.
            await robot.call(lambda: arm.get_joint_positions())
        Re-create resource clients from `self.machine` inside `op` if they might
        be stale after a reconnect; component clients here are looked up fresh.
        """
        attempts = (retries if retries is not None else self._max_call_retries)
        last: Optional[BaseException] = None
        for i in range(1, attempts + 1):
            try:
                return await op()
            except BaseException as exc:  # noqa: BLE001 — we re-raise non-conn errors
                if not _is_connection_error(exc):
                    raise
                last = exc
                if i < attempts:
                    backoff = min(0.5 * i, 2.0)
                    print(f"  [{label}] connection dropped ({type(exc).__name__}), "
                          f"reconnect + retry {i}/{attempts - 1} in {backoff:.1f}s")
                    await asyncio.sleep(backoff)
                    try:
                        await self._reconnect()
                    except Exception as re:
                        print(f"  [{label}] reconnect failed: {re}")
        raise RuntimeError(f"[{label}] failed after {attempts} attempts") from last

    # ---- typed resource accessors ------------------------------------------

    async def arm(self, name: str) -> Arm:
        return await self.call(lambda: _wrap(Arm.from_robot(self.machine, name)), label=f"arm:{name}")

    async def gripper(self, name: str) -> Gripper:
        return await self.call(lambda: _wrap(Gripper.from_robot(self.machine, name)), label=f"gripper:{name}")

    async def camera(self, name: str) -> Camera:
        return await self.call(lambda: _wrap(Camera.from_robot(self.machine, name)), label=f"cam:{name}")

    async def vision(self, name: str) -> VisionClient:
        return await self.call(lambda: _wrap(VisionClient.from_robot(self.machine, name)), label=f"vision:{name}")

    # ---- payload-aware camera helpers --------------------------------------

    async def get_color(self, cam_name: str = "cam-1"):
        """Pull the color image ONLY (small, stable). Use this in tracking loops —
        never pull depth at frame rate."""
        async def op():
            cam = Camera.from_robot(self.machine, cam_name)
            imgs, _ = await cam.get_images(filter_source_names=["color"], timeout=25)
            return next(i for i in imgs if i.name == "color")
        return await self.call(op, label="get_color")

    async def get_color_and_depth(self, cam_name: str = "cam-1"):
        """Pull color + depth (heavy: ~1.8 MB). Wrapped in retry because this is
        the exact call that drops WebRTC. Returns (color_img, depth_img)."""
        async def op():
            cam = Camera.from_robot(self.machine, cam_name)
            imgs, _ = await cam.get_images(timeout=40)
            color = next(i for i in imgs if i.name == "color")
            depth = next(i for i in imgs if i.name == "depth")
            return color, depth
        return await self.call(op, label="get_color_and_depth")

    # ---- lifecycle ----------------------------------------------------------

    async def close(self) -> None:
        if self._machine is not None:
            try:
                await self._machine.close()
            finally:
                self._machine = None

    async def __aenter__(self) -> "StableRobot":
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()


async def _wrap(x: T) -> T:
    """from_robot is sync; adapt it into the async `call` retry path."""
    return x


# --- depth helpers -----------------------------------------------------------

def decode_depth(depth_img) -> "tuple":
    """Decode Viam raw depth ('DEPTHMAP' + BE uint16 mm) into (numpy HxW float32 mm, w, h).
    Imported lazily so the module has no hard numpy dependency unless you use depth."""
    import numpy as np
    buf = depth_img.data
    assert buf[:8] == b"DEPTHMAP", buf[:8]
    w, h = struct.unpack(">QQ", buf[8:24])
    arr = np.frombuffer(buf[24:24 + w * h * 2], dtype=">u2").astype("float32").reshape(h, w)
    return arr, w, h
