"""Minimal motion.move camera tracker.

Watches the live YOLO feed, picks the biggest person, and re-aims the camera
at them through the motion service (planned, obstacle-aware whole-arm moves).
Angular errors come straight from the camera intrinsics, so a correction is
"rotate by GAIN * the true angle to the person" — no per-joint tuning.

Safety rails:
  - one move in flight at a time, each capped at MAX_STEP_DEG
  - the aim direction can never leave a CONE_DEG cone around home
    (no more staring at the ceiling)
  - subject lost for LOST_HOME_S -> one planned move back to home, then wait

Home pose = "straight ahead": captured from the CURRENT arm pose the first
time this runs and saved to home_pose.json. Re-capture (arm posed how you
want) with:  .venv/bin/python tracker_motion.py sethome

Run:  .venv/bin/python tracker_motion.py
Stop: Ctrl-C (stops the arm on exit).
"""

import asyncio
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

from viam.components.arm import Arm
from viam.proto.common import Pose, PoseInFrame
from viam.services.motion import MotionClient
from viam.services.vision import VisionClient
from viam.components.camera import Camera

from robot import ARM, CAMERA, GRIPPER, VISION_YOLO, connect

HOME_FILE = Path(__file__).parent / "home_pose.json"
LOG_DIR = Path(__file__).parent / "logs"

# --- Tunables ----------------------------------------------------------------
CONF_MIN = 0.5        # YOLO person confidence floor
DEADBAND_DEG = 3.0    # no move while the person is within this of center
GAIN = 0.85           # correct this fraction of the measured angle per move
MAX_STEP_DEG = 12.0   # cap per move
CONE_DEG = 40.0       # aim may never leave this cone around home
LOST_HOME_S = 3.0     # lost this long -> return home
POLL_S = 0.15         # detection poll while a move is in flight
YAW_SIGN = -1.0       # flip if it pans away from the person
PITCH_SIGN = 1.0      # flip if it tilts away from the person
# ----------------------------------------------------------------------------


def unit(v):
    v = np.array(v, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])


def rotate_dir(d, yaw_deg, pitch_deg):
    """Yaw about world z, then pitch about the horizontal axis. Small angles."""
    v = unit(d)
    yz = np.radians(yaw_deg)
    rz = np.array([[np.cos(yz), -np.sin(yz), 0.0],
                   [np.sin(yz), np.cos(yz), 0.0],
                   [0.0, 0.0, 1.0]])
    v = rz @ v
    axis = np.cross([0.0, 0.0, 1.0], v)
    n = np.linalg.norm(axis)
    if n > 1e-6:
        axis /= n
        p = np.radians(pitch_deg)
        v = (v * np.cos(p) + np.cross(axis, v) * np.sin(p)
             + axis * np.dot(axis, v) * (1.0 - np.cos(p)))
    return v


def cone_clamp(v, home, max_deg):
    """Pull v back inside the cone of max_deg around home."""
    v, home = unit(v), unit(home)
    ang = np.degrees(np.arccos(float(np.clip(np.dot(v, home), -1.0, 1.0))))
    if ang <= max_deg:
        return v
    axis = np.cross(home, v)
    n = np.linalg.norm(axis)
    if n < 1e-9:
        return home
    axis /= n
    p = np.radians(max_deg)
    return (home * np.cos(p) + np.cross(axis, home) * np.sin(p)
            + axis * np.dot(axis, home) * (1.0 - np.cos(p)))


async def find_aim_frame(motion):
    """Prefer aiming the camera frame; fall back to the gripper frame."""
    for name in (CAMERA, GRIPPER):
        try:
            pose = (await motion.get_pose(name, "world")).pose
            print(f"aiming frame: {name}")
            return name, pose
        except Exception as e:
            print(f"get_pose({name}) failed: {type(e).__name__}: {e}")
    raise RuntimeError("no aimable frame — check the frame system config")


def biggest_person(detections):
    people = [d for d in detections
              if d.class_name == "person" and d.confidence >= CONF_MIN]
    if not people:
        return None
    return max(people, key=lambda d: (d.x_max - d.x_min) * (d.y_max - d.y_min))


async def main():
    machine = await connect()
    arm = Arm.from_robot(machine, ARM)
    try:
        motion = MotionClient.from_robot(machine, "builtin")
        vision = VisionClient.from_robot(machine, VISION_YOLO)
        cam = Camera.from_robot(machine, CAMERA)
        ip = (await cam.get_properties()).intrinsic_parameters
        if not ip.focal_x_px:
            raise RuntimeError("no intrinsics from cam-1")

        rn, cur = await find_aim_frame(motion)

        if len(sys.argv) > 1 and sys.argv[1] == "sethome" or not HOME_FILE.exists():
            HOME_FILE.write_text(json.dumps({
                "x": cur.x, "y": cur.y, "z": cur.z,
                "o_x": cur.o_x, "o_y": cur.o_y, "o_z": cur.o_z, "theta": cur.theta,
            }, indent=2))
            print(f"home pose captured from current arm position -> {HOME_FILE.name}")
        home = json.loads(HOME_FILE.read_text())
        home_pose = Pose(**home)
        home_dir = unit([home["o_x"], home["o_y"], home["o_z"]])

        LOG_DIR.mkdir(exist_ok=True)
        log_path = LOG_DIR / f"motion_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        log_f = open(log_path, "w", newline="")
        log = csv.writer(log_f)
        log.writerow(["t", "phase", "yaw_err", "pitch_err", "move_s"])
        print(f"log: {log_path.name} | deadband {DEADBAND_DEG}° gain {GAIN} "
              f"cone {CONE_DEG}° | Ctrl-C to stop")

        move_task = None
        move_started = 0.0
        last_seen = time.monotonic()
        homed = True  # we start at home
        t0 = time.monotonic()
        err_since = None  # first failure of the current outage

        while True:
            try:
                person = biggest_person(await vision.get_detections_from_camera(CAMERA))
                err_since = None
            except Exception as e:
                # network blip: let the SDK re-dial and resume; give up after 60s
                if err_since is None:
                    err_since = time.monotonic()
                    print(f"!! connection trouble ({type(e).__name__}) — riding it out")
                elif time.monotonic() - err_since > 60:
                    print("!! outage exceeded 60s, giving up")
                    raise
                await asyncio.sleep(1.0)
                continue

            yaw_err = pitch_err = None
            if person is not None:
                u = (person.x_min + person.x_max) / 2.0
                v = (person.y_min + person.y_max) / 2.0   # box center
                yaw_err = np.degrees(np.arctan2(u - ip.center_x_px, ip.focal_x_px))
                pitch_err = np.degrees(np.arctan2(v - ip.center_y_px, ip.focal_y_px))
                last_seen = time.monotonic()
                homed = False

            move_s = None
            if move_task is not None and move_task.done():
                move_s = round(time.monotonic() - move_started, 2)
                exc = move_task.exception()
                if exc is not None:
                    print(f"!! motion.move failed ({type(exc).__name__}: {exc})")
                move_task = None

            phase = "idle"
            if move_task is not None:
                phase = "moving"
            elif person is not None:
                err = float(np.hypot(yaw_err, pitch_err))
                if err > DEADBAND_DEG:
                    try:
                        cur = (await motion.get_pose(rn, "world")).pose
                    except Exception as e:
                        print(f"!! get_pose failed ({type(e).__name__}) — skipping this correction")
                        await asyncio.sleep(1.0)
                        continue
                    yaw = float(np.clip(YAW_SIGN * GAIN * yaw_err, -MAX_STEP_DEG, MAX_STEP_DEG))
                    pitch = float(np.clip(PITCH_SIGN * GAIN * pitch_err, -MAX_STEP_DEG, MAX_STEP_DEG))
                    nd = cone_clamp(rotate_dir((cur.o_x, cur.o_y, cur.o_z), yaw, pitch),
                                    home_dir, CONE_DEG)
                    dest = Pose(x=cur.x, y=cur.y, z=cur.z,
                                o_x=nd[0], o_y=nd[1], o_z=nd[2], theta=cur.theta)
                    move_task = asyncio.create_task(motion.move(
                        component_name=rn,
                        destination=PoseInFrame(reference_frame="world", pose=dest)))
                    move_started = time.monotonic()
                    phase = "correct"
                    print(f"person at yaw {yaw_err:+.1f}° pitch {pitch_err:+.1f}° "
                          f"-> move ({yaw:+.1f}°, {pitch:+.1f}°)")
                else:
                    phase = "centered"
            elif not homed and time.monotonic() - last_seen > LOST_HOME_S:
                move_task = asyncio.create_task(motion.move(
                    component_name=rn,
                    destination=PoseInFrame(reference_frame="world", pose=home_pose)))
                move_started = time.monotonic()
                homed = True
                phase = "homing"
                print("subject lost -> returning to home framing")
            elif person is None:
                phase = "lost"

            log.writerow([round(time.monotonic() - t0, 2), phase,
                          None if yaw_err is None else round(yaw_err, 2),
                          None if pitch_err is None else round(pitch_err, 2),
                          move_s])
            log_f.flush()
            await asyncio.sleep(POLL_S)
    finally:
        try:
            await arm.stop()
        except Exception:
            pass
        await machine.close()


if __name__ == "__main__":
    asyncio.run(main())
