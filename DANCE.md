# Celebration dance + resilient connection

Two additions that pair with the existing `robot.py` / `cameraman.py`:

## `drk_robot.py` — `StableRobot`

A resilient wrapper around `RobotClient` for this machine. The machine is only
reachable over Viam's **WebRTC relay** (direct gRPC is refused — the robot is
NAT'd), and WebRTC drops the stream on sustained large payloads (most reliably
on repeated RealSense **depth** pulls, ~1.8 MB each). The stock client doesn't
retry a call whose stream died, so one blip aborts a whole routine.

`StableRobot` adds:

- **Tuned reconnect** — checks the link every 3 s (default 10), 7 reconnect
  attempts, 30 s timeouts.
- **`call()`** — runs any op and, on a connection-class error, rebuilds the
  client and retries with backoff. Your routine survives a dropped stream.
- **Payload-aware camera helpers** — `get_color()` pulls color-only (small,
  stable; use this in tracking loops) vs `get_color_and_depth()` (heavy, retry-
  wrapped, for one-shot 3D).
- Reads creds from `.env` / environment, same as `robot.py`
  (`VIAM_ADDRESS`, `VIAM_API_KEY`, `VIAM_API_KEY_ID`).

```python
from drk_robot import StableRobot

async with StableRobot.from_env() as robot:
    v = await robot.vision("vision-1-yolo")
    dets = await robot.call(lambda: v.get_detections_from_camera("cam-1"))
```

### Measured throughput on robot20 (WebRTC relay)

| Path | Latency | Use for |
|---|---|---|
| YOLO `get_detections_from_camera` (server-side) | ~140 ms, ~7 fps, 0 drops | **tracking loops** |
| color-only image | ~350 ms, ~3 fps, 0 drops | occasional frames |
| color + depth (1.8 MB) | 1–40 s, frequent drops (retried) | one-shot 3D only |

Takeaway: **never pull depth at frame rate.** Track on YOLO detections; pull
depth once when you commit to a grasp.

## `dance.py` — celebration routine

A continuous, self-healing "Celebration" (Kool & The Gang) dance. Joint-space
only, stays elevated over the base, never reaches table level.

- Loops the routine for `DANCE_SECONDS` (default 180), then **always** homes.
- **Self-heals** on the fly: `StableRobot` recovers dropped streams, and an
  xArm **servo fault** (`Servo motor N error`) is caught, cleared
  (`do_command {"clear_error": true}`), and the move retried — a mid-routine
  motor trip no longer stops the dance.
- Gripper "claps" as rhythmic accents; a `finally` block returns the arm to its
  exact start pose on any exit (budget, error, or Ctrl-C).

```bash
.venv/bin/python dance.py            # 3 min, then homes
DANCE_SECONDS=30 .venv/bin/python dance.py
```

**Safety:** joint moves are point-to-point at the arm's configured
`speed_degs_per_sec` (20), so motion is gentle but pauses briefly at each
waypoint (the module exposes no velocity blending). A preflight aborts if
another process is already driving the arm.
