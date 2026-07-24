"""Drawer open/close via yellow spherical handles.

The drawer front faces world +X: it opens by pulling a handle +X and closes
by pushing back -X to the recorded closed position.

Pipeline: vision-yellow (color_detector) finds handle blobs -> robust median
depth at blob center -> deproject via intrinsics -> transform_pose cam-1 ->
world. Grasps and the pull/push run through the motion service; the pull and
push use a LinearConstraint so the gripper moves in a straight line along the
drawer's travel instead of a planned arc.

Run the stages IN ORDER, verifying each before the next (arm moves from
'dryrun' onward — human watching, workspace clear):

  .venv/bin/python drawer.py detect   # world positions of handles (NO motion)
  .venv/bin/python drawer.py dryrun   # approach + retreat, gripper never closes
  .venv/bin/python drawer.py open     # grasp, pull +X PULL_MM, release, retreat
  .venv/bin/python drawer.py close    # re-grasp at open pos, push home, release

State: 'open' records the closed/open handle X in drawer_state.json; 'close'
pushes back to the recorded closed X (ground truth beats re-detection).
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import numpy as np

from viam.components.camera import Camera
from viam.components.gripper import Gripper
from viam.media.video import CameraMimeType
from viam.proto.common import Pose, PoseInFrame
from viam.proto.service.motion import Constraints, LinearConstraint
from viam.services.motion import MotionClient
from viam.services.vision import VisionClient

from robot import CAMERA, GRIPPER, connect

VISION_YELLOW = "vision-yellow"
STATE_FILE = Path(__file__).parent / "drawer_state.json"

# --- Tunables ----------------------------------------------------------------
PULL_MM = 25.0          # open stroke along +X
APPROACH_MM = 80.0      # pre-grasp standoff in +X from the handle
RETREAT_MM = 80.0       # retreat distance after release
GRASP_ORIENT = dict(o_x=-1.0, o_y=0.0, o_z=0.0, theta=0.0)  # gripper faces -X
LINEAR_TOL_MM = 5.0     # straight-line tolerance for pull/push moves
MIN_Z_MM, MAX_Z_MM = 20.0, 400.0    # handle must be above table, below this
MAX_REACH_MM = 700.0    # sanity: handle within arm reach
REPEAT_TOL_MM = 30.0    # detect: two captures must agree within this
# ----------------------------------------------------------------------------

LINEAR = Constraints(linear_constraint=[LinearConstraint(line_tolerance_mm=LINEAR_TOL_MM)])


def robust_depth(depth: np.ndarray, u: int, v: int):
    """Median depth (mm) near (u,v); spheres are solid depth targets, but
    escalate the patch anyway in case the center pixel is a dropout."""
    h, w = depth.shape
    for r in (4, 8, 16):
        patch = depth[max(0, v - r):min(h, v + r + 1), max(0, u - r):min(w, u + r + 1)]
        valid = patch[(patch > 100) & (patch < 3000)]
        if valid.size >= 8:
            return float(np.median(valid))
    return None


async def capture_handles(machine) -> list[Pose]:
    """One capture: yellow blobs -> world-frame handle poses (grasp-oriented)."""
    cam = Camera.from_robot(machine, CAMERA)
    vision = VisionClient.from_robot(machine, VISION_YELLOW)

    props = await cam.get_properties()
    ip = props.intrinsic_parameters
    images, _ = await cam.get_images()
    depth = next((np.array(i.bytes_to_depth_array(), dtype=np.uint16)
                  for i in images if i.mime_type == CameraMimeType.VIAM_RAW_DEPTH), None)
    if depth is None:
        raise RuntimeError("no depth image from cam-1")

    handles = []
    for d in await vision.get_detections_from_camera(CAMERA):
        u = int((d.x_min + d.x_max) / 2)
        v = int((d.y_min + d.y_max) / 2)
        z = robust_depth(depth, u, v)
        if z is None:
            print(f"  blob at ({u},{v}): depth dropout, skipped")
            continue
        xc = (u - ip.center_x_px) * z / ip.focal_x_px
        yc = (v - ip.center_y_px) * z / ip.focal_y_px
        pif = PoseInFrame(reference_frame=CAMERA,
                          pose=Pose(x=xc, y=yc, z=z, o_x=0, o_y=0, o_z=1, theta=0))
        world = (await machine.transform_pose(pif, "world")).pose
        if not (MIN_Z_MM <= world.z <= MAX_Z_MM):
            print(f"  blob -> world z={world.z:.0f}mm outside table band, skipped")
            continue
        if (world.x ** 2 + world.y ** 2) ** 0.5 > MAX_REACH_MM:
            print(f"  blob -> ({world.x:.0f},{world.y:.0f}) beyond reach, skipped")
            continue
        handles.append(Pose(x=world.x, y=world.y, z=world.z, **GRASP_ORIENT))
    return handles


async def locate_primary_handle(machine) -> Pose:
    """Two captures; the primary handle must repeat within REPEAT_TOL_MM."""
    a = await capture_handles(machine)
    if not a:
        raise RuntimeError("no yellow handles found (check vision-yellow panel/lighting)")
    await asyncio.sleep(0.3)
    b = await capture_handles(machine)
    best = a[0]
    for h2 in b:
        dist = ((best.x - h2.x) ** 2 + (best.y - h2.y) ** 2 + (best.z - h2.z) ** 2) ** 0.5
        if dist <= REPEAT_TOL_MM:
            return Pose(x=(best.x + h2.x) / 2, y=(best.y + h2.y) / 2,
                        z=(best.z + h2.z) / 2, **GRASP_ORIENT)
    raise RuntimeError(f"handle position not repeatable within {REPEAT_TOL_MM}mm across captures")


def offset_x(p: Pose, dx: float) -> Pose:
    return Pose(x=p.x + dx, y=p.y, z=p.z, **GRASP_ORIENT)


async def move_gripper(machine, dest: Pose, linear: bool = False):
    motion = MotionClient.from_robot(machine, "builtin")
    ok = await motion.move(
        component_name=GRIPPER,
        destination=PoseInFrame(reference_frame="world", pose=dest),
        constraints=LINEAR if linear else None,
    )
    if not ok:
        raise RuntimeError(f"motion.move failed to ({dest.x:.0f},{dest.y:.0f},{dest.z:.0f})")


async def approach_and_grasp(machine, handle: Pose, really_grip: bool) -> bool:
    """Pre-grasp -> open -> linear advance to handle -> (grab). Returns grab result."""
    gripper = Gripper.from_robot(machine, GRIPPER)
    await move_gripper(machine, offset_x(handle, APPROACH_MM))
    await gripper.open()
    await move_gripper(machine, handle, linear=True)
    if not really_grip:
        return True
    grabbed = await gripper.grab()
    if not grabbed:
        print("!! grab closed on nothing — missed the sphere; retreating")
        await gripper.open()
        await move_gripper(machine, offset_x(handle, APPROACH_MM), linear=True)
    return grabbed


async def release_and_retreat(machine, at: Pose):
    gripper = Gripper.from_robot(machine, GRIPPER)
    await gripper.open()
    await move_gripper(machine, offset_x(at, RETREAT_MM), linear=True)


async def cmd_detect(machine):
    handles = await capture_handles(machine)
    print(f"{len(handles)} handle(s):")
    for h in handles:
        print(f"  world ({h.x:.0f}, {h.y:.0f}, {h.z:.0f}) mm")
    if handles:
        primary = await locate_primary_handle(machine)
        print(f"primary (repeatability-checked): ({primary.x:.0f}, {primary.y:.0f}, {primary.z:.0f})")


async def cmd_dryrun(machine):
    handle = await locate_primary_handle(machine)
    print(f"dry run to ({handle.x:.0f}, {handle.y:.0f}, {handle.z:.0f}) — gripper stays open")
    await approach_and_grasp(machine, handle, really_grip=False)
    time.sleep(1.0)  # pause at grasp pose so a human can eyeball alignment
    await move_gripper(machine, offset_x(handle, APPROACH_MM), linear=True)
    print("dry run complete: approach + retreat, no contact commanded")


async def cmd_open(machine):
    handle = await locate_primary_handle(machine)
    print(f"opening: handle at ({handle.x:.0f}, {handle.y:.0f}, {handle.z:.0f})")
    if not await approach_and_grasp(machine, handle, really_grip=True):
        raise RuntimeError("grasp failed")
    open_pose = offset_x(handle, PULL_MM)
    await move_gripper(machine, open_pose, linear=True)   # the pull
    STATE_FILE.write_text(json.dumps({
        "closed": {"x": handle.x, "y": handle.y, "z": handle.z},
        "open": {"x": open_pose.x, "y": open_pose.y, "z": open_pose.z},
        "opened_at": time.time(),
    }, indent=2))
    await release_and_retreat(machine, open_pose)
    print(f"drawer open (+{PULL_MM:.0f}mm); state saved to {STATE_FILE.name}")


async def cmd_close(machine):
    if not STATE_FILE.exists():
        raise RuntimeError("no drawer_state.json — run 'open' first (or drawer already closed)")
    st = json.loads(STATE_FILE.read_text())
    open_pose = Pose(**st["open"], **GRASP_ORIENT)
    closed_pose = Pose(**st["closed"], **GRASP_ORIENT)
    print(f"closing: re-grasp at ({open_pose.x:.0f}, {open_pose.y:.0f}, {open_pose.z:.0f}), "
          f"push to x={closed_pose.x:.0f}")
    if not await approach_and_grasp(machine, open_pose, really_grip=True):
        raise RuntimeError("grasp failed")
    await move_gripper(machine, closed_pose, linear=True)  # the push
    await release_and_retreat(machine, closed_pose)
    STATE_FILE.unlink()
    print("drawer closed and returned to original position")


COMMANDS = {"detect": cmd_detect, "dryrun": cmd_dryrun, "open": cmd_open, "close": cmd_close}


async def main():
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    machine = await connect()
    try:
        await COMMANDS[sys.argv[1]](machine)
    finally:
        await machine.close()


if __name__ == "__main__":
    asyncio.run(main())
