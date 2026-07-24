"""MVP1 — Cameraman: keep the primary person centered in the wrist cam.

Pans the arm's base joint (J1) toward the tracked person's horizontal offset
from frame center, with a deadband so it doesn't oscillate.

Primary-person policy:
  - Acquire: the person nearest frame center, and only if they're inside the
    middle CENTER_ACQUIRE_FRAC of the frame — your subject "claims" the camera
    by stepping to center; people at the edges can't steal acquisition.
  - Lock: on later frames, follow the box whose center is nearest the last
    known center (within MATCH_MAX_FRAC of frame width) AND whose size is
    similar (within SIZE_RATIO_MAX) — a passerby crossing close to the lens
    shows up much larger and is rejected, so the lock doesn't transfer.
  - Occlusion: on a miss the arm holds its last position and the lock's last
    location is remembered; if the subject reappears near it within
    LOST_FRAMES ticks, tracking resumes. Only after LOST_FRAMES consecutive
    misses does the lock drop, and re-acquisition again requires center.

Run:  .venv/bin/python cameraman.py
Stop: Ctrl-C (stops the arm on exit).
"""

import asyncio

from viam.components.arm import Arm
from viam.components.camera import Camera
from viam.proto.component.arm import JointPositions
from viam.services.vision import VisionClient

from robot import ARM, CAMERA, VISION_YOLO, connect

# --- Tunables (adjust under venue lighting) ---------------------------------
CONF_MIN = 0.5          # YOLO confidence floor for person boxes
LOOP_HZ = 2.5           # detection/control rate
DEADBAND_FRAC = 0.12    # no motion while |offset| < 12% of half-width ("center third" ~ 0.33/2)
KP_DEG = 6.0            # pan step (deg) at full-frame-edge offset
MAX_STEP_DEG = 4.0      # per-tick pan clamp, keeps motion smooth at 20 deg/s
PAN_SIGN = -1.0         # flip to +1.0 if the arm pans away from the person
J1_LIMIT_DEG = 100.0    # keep base joint within +/- this range
LOST_FRAMES = 8         # ticks (~3.2s) without a match before dropping the lock
ACQUIRE_FRAMES = 2      # consecutive ticks seen before we start moving
MATCH_MAX_FRAC = 0.35   # lock match radius, as fraction of frame width
CENTER_ACQUIRE_FRAC = 0.5  # new subject must be inside the middle 50% of frame
SIZE_RATIO_MAX = 2.5    # reject lock match if box area changes more than this
# ----------------------------------------------------------------------------


def box_center_x(d) -> float:
    return (d.x_min + d.x_max) / 2.0


def box_area(d) -> float:
    return max(0, d.x_max - d.x_min) * max(0, d.y_max - d.y_min)


class PersonTracker:
    """Sticky nearest-neighbor lock on one person."""

    def __init__(self, frame_width: int):
        self.frame_width = frame_width
        self.last_cx: float | None = None
        self.last_area: float | None = None
        self.seen_streak = 0
        self.miss_streak = 0

    def update(self, detections) -> float | None:
        """Returns the tracked person's center-x, or None if not tracking."""
        people = [d for d in detections
                  if d.class_name == "person" and d.confidence >= CONF_MIN]
        if not people:
            return self._miss()

        if self.last_cx is None:
            target = self._acquire(people)
        else:
            target = self._match(people)
        if target is None:
            return self._miss()

        self.last_cx = box_center_x(target)
        self.last_area = box_area(target)
        self.seen_streak += 1
        self.miss_streak = 0
        if self.seen_streak < ACQUIRE_FRAMES:
            return None  # debounce: don't chase one-frame blips
        return self.last_cx

    def _acquire(self, people):
        """New subject: the person nearest frame center, if inside the center zone."""
        mid = self.frame_width / 2.0
        candidate = min(people, key=lambda d: abs(box_center_x(d) - mid))
        if abs(box_center_x(candidate) - mid) > CENTER_ACQUIRE_FRAC * mid:
            return None  # nobody near center; wait for the subject to step in
        return candidate

    def _match(self, people):
        """Locked: nearest box to last position, gated by distance and size."""
        target = min(people, key=lambda d: abs(box_center_x(d) - self.last_cx))
        if abs(box_center_x(target) - self.last_cx) > MATCH_MAX_FRAC * self.frame_width:
            return None
        area = box_area(target)
        if self.last_area and area > 0:
            ratio = max(area / self.last_area, self.last_area / area)
            if ratio > SIZE_RATIO_MAX:
                return None  # sudden size jump: likely a passerby, not our subject
        return target

    def _miss(self) -> None:
        self.seen_streak = 0
        self.miss_streak += 1
        if self.miss_streak >= LOST_FRAMES:
            self.last_cx = None  # drop lock; next sighting re-acquires
            self.last_area = None
        return None


async def get_frame_width(camera: Camera) -> int:
    props = await camera.get_properties()
    w = props.intrinsic_parameters.width_px
    if w:
        return w
    raise RuntimeError("camera did not report width_px; set frame width manually")


async def main():
    machine = await connect()
    try:
        arm = Arm.from_robot(machine, ARM)
        camera = Camera.from_robot(machine, CAMERA)
        vision = VisionClient.from_robot(machine, VISION_YOLO)

        width = await get_frame_width(camera)
        half = width / 2.0
        tracker = PersonTracker(width)
        print(f"tracking on {width}px frame, deadband ±{DEADBAND_FRAC * half:.0f}px")

        period = 1.0 / LOOP_HZ
        while True:
            t0 = asyncio.get_event_loop().time()

            detections = await vision.get_detections_from_camera(CAMERA)
            cx = tracker.update(detections)

            if cx is not None:
                offset = (cx - half) / half  # -1 (left edge) .. +1 (right edge)
                if abs(offset) > DEADBAND_FRAC:
                    step = max(-MAX_STEP_DEG, min(MAX_STEP_DEG, PAN_SIGN * KP_DEG * offset))
                    joints = await arm.get_joint_positions()
                    j = list(joints.values)
                    j[0] = max(-J1_LIMIT_DEG, min(J1_LIMIT_DEG, j[0] + step))
                    await arm.move_to_joint_positions(JointPositions(values=j))
                    print(f"offset {offset:+.2f} -> pan {step:+.1f}° (J1 {j[0]:+.1f}°)")
                else:
                    print(f"offset {offset:+.2f} (centered)")
            else:
                print("no lock")

            elapsed = asyncio.get_event_loop().time() - t0
            await asyncio.sleep(max(0.0, period - elapsed))
    finally:
        try:
            await Arm.from_robot(machine, ARM).stop()
        except Exception:
            pass
        await machine.close()


if __name__ == "__main__":
    asyncio.run(main())
