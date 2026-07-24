"""MVP1 — Cameraman: keep the primary person centered in the wrist cam.

Two-axis smooth follow: J1 pans (horizontal) and J5 tilts (vertical, aimed at
the subject's upper body). Control per axis: EMA-filtered offset, deadband
with hysteresis, proportional step + velocity feedforward, slew-rate ramp.
Walking subjects get lead room (framed slightly behind their motion).

Primary-person policy (busy-room hardened):
  - Candidates must be >= min_height_frac of frame height (filters background
    crowd) and >= conf_min confidence.
  - Acquire: person nearest frame center, inside the middle center_acquire_frac
    of frame — the subject claims the camera by stepping to center.
  - Lock: nearest box to last position, gated by match radius and box-size
    ratio so passersby can't steal the lock.
  - Lost: after lost_frames misses the lock drops; after search_after_s the
    arm eases back to its startup framing and waits for a new center claim.

Live tuning: edit tracker_tuning.json while running — it hot-reloads within a
second (no restart). Every tick is appended to logs/track_*.csv for offline
tuning analysis.

Run:  .venv/bin/python cameraman.py
Stop: Ctrl-C (stops the arm on exit).
"""

import asyncio
import csv
import json
import time
from pathlib import Path

import numpy as np

from viam.components.arm import Arm
from viam.components.camera import Camera
from viam.proto.common import Pose, PoseInFrame, ResourceName
from viam.proto.component.arm import JointPositions
from viam.services.motion import MotionClient
from viam.services.vision import VisionClient

from robot import ARM, CAMERA, VISION_YOLO, connect

CAM_RN = ResourceName(namespace="rdk", type="component", subtype="camera", name=CAMERA)

TUNING_FILE = Path(__file__).parent / "tracker_tuning.json"
LOG_DIR = Path(__file__).parent / "logs"

DEFAULTS = {
    # loop / detection
    "loop_hz": 4.0,
    "conf_min": 0.5,
    "stale_tick_s": 0.7,        # skip motion if the detection round-trip took longer
    # pan (J1, horizontal)
    "pan_sign": -1.0,           # flip if the arm pans away from the person
    "kp_deg": 6.0,
    "ff_gain": 1.5,             # feedforward deg per (offset/sec): cuts lag w/o overshoot
    "max_step_deg": 3.0,
    "slew_deg": 1.2,            # max step change per tick (accel/decel ramp)
    "deadband_enter": 0.12,
    "deadband_exit": 0.05,
    "ema_alpha": 0.5,           # 1.0 raw/jittery .. 0.2 heavy/laggy
    "j1_limit_deg": 100.0,
    # lead room (cinematic framing ahead of a walking subject)
    "lead_room_frac": 0.08,     # target offset behind motion direction
    "lead_vel_min": 0.08,       # offset/sec of subject motion before lead engages
    # motion mode: aim the camera frame via the motion service. Experimental —
    # keep False for demos; joint mode is the proven path.
    "use_motion_service": False,
    # home pose for lost-subject search. null = capture arm pose at startup —
    # only safe if the arm is framing the scene when the script starts. Set
    # explicit degrees here to pin a known-good home.
    "j1_home": None,
    "j5_home": None,
    # tilt (vertical — aims at box center)
    "tilt_enabled": True,
    "tilt_sign": -1.0,          # flip if tilt moves the wrong way
    "tilt_target_frac": 0.50,   # keep the aim point at frame center
    "tilt_kp_deg": 3.0,
    "tilt_max_step_deg": 1.2,   # gentle: tilt overshoot loses the lock (see 1511 log)
    "tilt_slew_deg": 0.8,
    "tilt_deadband_enter": 0.10,
    "tilt_deadband_exit": 0.05,
    "tilt_range_deg": 25.0,     # J5 stays within this of its startup angle
    # busy-room person gating
    "min_height_frac": 0.30,
    "match_max_frac": 0.22,
    "size_ratio_max": 2.0,
    "center_acquire_frac": 0.5,
    "acquire_frames": 2,
    "lost_frames": 12,
    # lost-subject behavior
    "search_after_s": 4.0,      # lost this long -> ease back to startup framing
    "search_step_deg": 0.5,
}


def load_tuning() -> dict:
    if not TUNING_FILE.exists():
        TUNING_FILE.write_text(json.dumps(DEFAULTS, indent=2) + "\n")
        return dict(DEFAULTS)
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(TUNING_FILE.read_text()))
    except json.JSONDecodeError as e:
        print(f"!! tracker_tuning.json invalid ({e}); keeping previous values")
    return cfg


def box_center_x(d) -> float:
    return (d.x_min + d.x_max) / 2.0


def box_aim_y(d) -> float:
    """Aim point: center of the person's bounding box."""
    return d.y_min + 0.5 * (d.y_max - d.y_min)


def rotate_dir(d, yaw_deg: float, pitch_deg: float) -> np.ndarray:
    """Rotate a pointing direction: yaw about world z, then pitch about the
    horizontal axis perpendicular to it. Small corrective rotations only."""
    v = np.array(d, dtype=float)
    n = np.linalg.norm(v)
    v = v / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])
    yz = np.radians(yaw_deg)
    rz = np.array([[np.cos(yz), -np.sin(yz), 0.0],
                   [np.sin(yz), np.cos(yz), 0.0],
                   [0.0, 0.0, 1.0]])
    v = rz @ v
    axis = np.cross([0.0, 0.0, 1.0], v)
    an = np.linalg.norm(axis)
    if an > 1e-6:
        axis = axis / an
        p = np.radians(pitch_deg)
        v = (v * np.cos(p) + np.cross(axis, v) * np.sin(p)
             + axis * np.dot(axis, v) * (1.0 - np.cos(p)))
    return v


def box_area(d) -> float:
    return max(0, d.x_max - d.x_min) * max(0, d.y_max - d.y_min)


class PersonTracker:
    """Sticky nearest-neighbor lock on one person."""

    def __init__(self, frame_width: int, frame_height: int):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.last_cx: float | None = None
        self.last_area: float | None = None
        self.seen_streak = 0
        self.miss_streak = 0

    def update(self, detections, cfg) -> tuple[float, float] | None:
        """Returns (center_x, aim_y) of the tracked person, or None."""
        people = [d for d in detections
                  if d.class_name == "person" and d.confidence >= cfg["conf_min"]
                  and (d.y_max - d.y_min) >= cfg["min_height_frac"] * self.frame_height]
        if not people:
            return self._miss(cfg)

        if self.last_cx is None:
            target = self._acquire(people, cfg)
        else:
            target = self._match(people, cfg)
        if target is None:
            return self._miss(cfg)

        self.last_cx = box_center_x(target)
        self.last_area = box_area(target)
        self.seen_streak += 1
        self.miss_streak = 0
        if self.seen_streak < cfg["acquire_frames"]:
            return None  # debounce: don't chase one-frame blips
        return self.last_cx, box_aim_y(target)

    def _acquire(self, people, cfg):
        mid = self.frame_width / 2.0
        candidate = min(people, key=lambda d: abs(box_center_x(d) - mid))
        if abs(box_center_x(candidate) - mid) > cfg["center_acquire_frac"] * mid:
            return None  # nobody near center; wait for the subject to step in
        return candidate

    def _match(self, people, cfg):
        target = min(people, key=lambda d: abs(box_center_x(d) - self.last_cx))
        if abs(box_center_x(target) - self.last_cx) > cfg["match_max_frac"] * self.frame_width:
            return None
        area = box_area(target)
        if self.last_area and area > 0:
            ratio = max(area / self.last_area, self.last_area / area)
            if ratio > cfg["size_ratio_max"]:
                return None  # sudden size jump: likely a passerby, not our subject
        return target

    def _miss(self, cfg) -> None:
        self.seen_streak = 0
        self.miss_streak += 1
        if self.miss_streak >= cfg["lost_frames"]:
            self.last_cx = None
            self.last_area = None
        return None


class AxisController:
    """EMA + deadband hysteresis + P/feedforward + slew ramp for one joint."""

    def __init__(self, prefix: str):
        self.p = prefix  # "" for pan keys, "tilt_" for tilt keys
        self.ema = 0.0
        self.vel = 0.0          # smoothed d(offset)/dt, per second
        self.prev_step = 0.0
        self.correcting = False

    def k(self, cfg, name, pan_name=None):
        return cfg[self.p + name if self.p else (pan_name or name)]

    def update(self, raw: float | None, target: float, dt: float, cfg) -> float:
        """raw offset in -1..+1 (None = subject not visible). Returns step (deg)."""
        alpha = cfg["ema_alpha"]
        if raw is None:
            self.ema *= (1 - alpha)  # decay toward 0 while blind
            self.vel *= 0.5
            self.correcting = False
            desired = 0.0
        else:
            prev_ema = self.ema
            self.ema = alpha * raw + (1 - alpha) * self.ema
            if dt > 0:
                self.vel = 0.6 * self.vel + 0.4 * ((self.ema - prev_ema) / dt)
            error = self.ema - target
            enter = self.k(cfg, "deadband_enter")
            exit_ = self.k(cfg, "deadband_exit")
            self.correcting = abs(error) > (exit_ if self.correcting else enter)
            if self.correcting:
                sign = self.k(cfg, "sign", "pan_sign")
                desired = sign * (self.k(cfg, "kp_deg") * error
                                  + cfg["ff_gain"] * self.vel)
            else:
                desired = 0.0
            # gains are tuned per 250ms tick; scale by real elapsed time so a
            # slow network tick takes a proportionally bigger step (same deg/s)
            scale = min(max(dt / 0.25, 1.0), 4.0)
            desired *= scale
            limit = self.k(cfg, "max_step_deg") * scale
            desired = max(-limit, min(limit, desired))

        scale = min(max(dt / 0.25, 1.0), 4.0)
        slew = self.k(cfg, "slew_deg") * scale
        step = self.prev_step + max(-slew, min(slew, desired - self.prev_step))
        self.prev_step = step
        return step


async def main():
    cfg = load_tuning()
    machine = await connect()
    arm = Arm.from_robot(machine, ARM)
    try:
        camera = Camera.from_robot(machine, CAMERA)
        vision = VisionClient.from_robot(machine, VISION_YOLO)

        props = await camera.get_properties()
        width = props.intrinsic_parameters.width_px
        height = props.intrinsic_parameters.height_px
        if not (width and height):
            raise RuntimeError("camera did not report frame size")
        half_w, half_h = width / 2.0, height / 2.0

        start_joints = list((await arm.get_joint_positions()).values)
        j1_home = cfg["j1_home"] if cfg.get("j1_home") is not None else start_joints[0]
        j5_home = cfg["j5_home"] if cfg.get("j5_home") is not None else start_joints[4]
        print(f"home framing: J1 {j1_home:+.1f}° J5 {j5_home:+.1f}° "
              f"({'from tuning file' if cfg.get('j1_home') is not None else 'captured at startup — jog the arm to good framing BEFORE starting'})")

        motion = MotionClient.from_robot(machine, "builtin")
        motion_ok = False
        start_cam_pose = None
        try:
            start_cam_pose = (await motion.get_pose(CAM_RN, "world")).pose
            motion_ok = True
        except Exception as e:
            print(f"!! motion service unavailable ({type(e).__name__}); using joint mode")

        tracker = PersonTracker(width, height)
        pan = AxisController("")
        tilt = AxisController("tilt_")

        LOG_DIR.mkdir(exist_ok=True)
        log_path = LOG_DIR / f"track_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        log_f = open(log_path, "w", newline="")
        log = csv.writer(log_f)
        log.writerow(["t", "state", "raw_x", "ema_x", "vel_x", "step_pan",
                      "raw_y", "step_tilt", "j1", "j5", "det_s", "tick_s"])

        print(f"tracking {width}x{height} | tuning: {TUNING_FILE.name} (hot-reloads) | log: {log_path.name}")

        tuning_mtime = TUNING_FILE.stat().st_mtime
        last_seen = time.monotonic()
        last_tick = time.monotonic()
        t_start = time.monotonic()
        err_since = None  # first failure time of the current outage, None = healthy
        move_task = None  # in-flight motion-service move, one at a time
        searched = False  # search move already issued for this lost episode

        while True:
            t0 = time.monotonic()
            dt = t0 - last_tick
            last_tick = t0

            # hot-reload tuning on file change
            mtime = TUNING_FILE.stat().st_mtime
            if mtime != tuning_mtime:
                tuning_mtime = mtime
                cfg = load_tuning()
                print(">> tuning reloaded")

            try:
                det_t0 = time.monotonic()
                detections = await vision.get_detections_from_camera(CAMERA)
                det_s = time.monotonic() - det_t0
            except Exception as e:
                # network stall / expired session: wind down, let the SDK
                # re-dial, and resume — abort only if the outage persists.
                if err_since is None:
                    err_since = time.monotonic()
                    print(f"!! robot call failed ({type(e).__name__}: {e}) — riding out the reconnect")
                elif time.monotonic() - err_since > 60:
                    print("!! outage exceeded 60s, giving up")
                    raise
                pan.update(None, 0.0, dt, cfg)
                tilt.update(None, 0.0, dt, cfg)
                log.writerow([round(time.monotonic() - t_start, 2), "error"] + [None] * 10)
                log_f.flush()
                print(f"[error ] {type(e).__name__}; retrying")
                await asyncio.sleep(1.0)
                continue
            err_since = None

            hit = tracker.update(detections, cfg)
            raw_x = raw_y = None
            if hit is not None:
                cx, aim_y = hit
                raw_x = (cx - half_w) / half_w          # -1 left .. +1 right
                raw_y = (aim_y - cfg["tilt_target_frac"] * height) / half_h
                last_seen = time.monotonic()

            stale = det_s > cfg["stale_tick_s"]
            if stale:
                state = "stale"
                step_pan = pan.update(None, 0.0, dt, cfg)   # wind down, don't act on old data
                step_tilt = tilt.update(None, 0.0, dt, cfg)
            else:
                # lead room: aim slightly behind a walking subject's motion
                lead = 0.0
                if raw_x is not None and abs(pan.vel) > cfg["lead_vel_min"]:
                    lead = cfg["lead_room_frac"] * (1 if pan.vel > 0 else -1)
                step_pan = pan.update(raw_x, lead, dt, cfg)
                step_tilt = tilt.update(raw_y, 0.0, dt, cfg) if cfg["tilt_enabled"] else 0.0
                state = "lock" if raw_x is not None else "lost"

            searching = (state == "lost"
                         and time.monotonic() - last_seen > cfg["search_after_s"])

            j1_now = j5_now = float("nan")
            want_move = abs(step_pan) > 0.05 or abs(step_tilt) > 0.05 or searching
            try:
                if motion_ok and cfg.get("use_motion_service", True):
                    # -- motion-service mode: re-aim the camera frame with
                    # planned moves; one in flight at a time --
                    if move_task is not None and move_task.done():
                        exc = move_task.exception()
                        if exc is not None:
                            print(f"!! motion.move failed ({type(exc).__name__}: {exc})")
                        move_task = None
                    if state == "lock":
                        searched = False
                    if move_task is not None:
                        state += "*"  # move in flight
                    elif want_move and not (searching and searched):
                        if searching:
                            dest = start_cam_pose
                            state = "search"
                            searched = True
                        else:
                            cur = (await motion.get_pose(CAM_RN, "world")).pose
                            nd = rotate_dir((cur.o_x, cur.o_y, cur.o_z), step_pan, step_tilt)
                            dest = Pose(x=cur.x, y=cur.y, z=cur.z,
                                        o_x=nd[0], o_y=nd[1], o_z=nd[2], theta=cur.theta)
                        move_task = asyncio.create_task(motion.move(
                            component_name=CAM_RN,
                            destination=PoseInFrame(reference_frame="world", pose=dest)))
                        pan.prev_step = tilt.prev_step = 0.0
                elif want_move:
                    # -- joint mode fallback --
                    joints = await arm.get_joint_positions()
                    j = list(joints.values)
                    if searching:
                        # ease back to startup framing, wait for a new center claim
                        for idx, home, rate in ((0, j1_home, cfg["search_step_deg"]),
                                                (4, j5_home, cfg["search_step_deg"])):
                            delta = home - j[idx]
                            j[idx] += max(-rate, min(rate, delta))
                        state = "search"
                    else:
                        lim = cfg["j1_limit_deg"]
                        j[0] = max(-lim, min(lim, j[0] + step_pan))
                        lo, hi = j5_home - cfg["tilt_range_deg"], j5_home + cfg["tilt_range_deg"]
                        j[4] = max(lo, min(hi, j[4] + step_tilt))
                    await arm.move_to_joint_positions(JointPositions(values=j))
                    j1_now, j5_now = j[0], j[4]
            except Exception as e:
                if err_since is None:
                    err_since = time.monotonic()
                    print(f"!! move failed ({type(e).__name__}: {e}) — riding out the reconnect")
                elif time.monotonic() - err_since > 60:
                    print("!! outage exceeded 60s, giving up")
                    raise
                state = "error"
                pan.prev_step = 0.0   # restart motion from a ramp, not a jump
                tilt.prev_step = 0.0
                await asyncio.sleep(1.0)

            tick_s = time.monotonic() - t0
            log.writerow([round(time.monotonic() - t_start, 2), state,
                          _r(raw_x), _r(pan.ema), _r(pan.vel), _r(step_pan),
                          _r(raw_y), _r(step_tilt), _r(j1_now), _r(j5_now),
                          round(det_s, 3), round(tick_s, 3)])
            log_f.flush()
            print(f"[{state:6s}] x {pan.ema:+.2f} y {tilt.ema:+.2f} v {pan.vel:+.2f} "
                  f"pan {step_pan:+.2f}° tilt {step_tilt:+.2f}° det {det_s * 1000:.0f}ms")

            await asyncio.sleep(max(0.0, 1.0 / cfg["loop_hz"] - (time.monotonic() - t0)))
    finally:
        try:
            await arm.stop()
        except Exception:
            pass
        await machine.close()


def _r(v):
    return None if v is None else (round(v, 3) if v == v else None)  # NaN -> None


if __name__ == "__main__":
    asyncio.run(main())
