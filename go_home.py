"""Move the camera back to the saved home pose (home_pose.json).

Usage:  .venv/bin/python go_home.py
Or from other code:  from go_home import go_home; await go_home(machine)

Do NOT run while a tracker script is commanding the arm — stop it first.
Home is the pose saved by tracker_motion.py ('sethome' to re-capture).
"""

import asyncio
import json
from pathlib import Path

from viam.proto.common import Pose, PoseInFrame
from viam.services.motion import MotionClient

from robot import CAMERA, connect

HOME_FILE = Path(__file__).parent / "home_pose.json"


async def go_home(machine) -> None:
    if not HOME_FILE.exists():
        raise RuntimeError("no home_pose.json — run 'tracker_motion.py sethome' first")
    home = json.loads(HOME_FILE.read_text())
    motion = MotionClient.from_robot(machine, "builtin")
    ok = await motion.move(
        component_name=CAMERA,
        destination=PoseInFrame(reference_frame="world", pose=Pose(**home)),
    )
    if not ok:
        raise RuntimeError("motion.move to home failed")
    print(f"at home: ({home['x']:.0f}, {home['y']:.0f}, {home['z']:.0f}) "
          f"facing ({home['o_x']:.2f}, {home['o_y']:.2f}, {home['o_z']:.2f})")


async def main():
    machine = await connect()
    try:
        await go_home(machine)
    finally:
        await machine.close()


if __name__ == "__main__":
    asyncio.run(main())
