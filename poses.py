"""Named arm poses: save the current position under a name, return to it later.

  .venv/bin/python poses.py save "look at phone"   # record current joints
  .venv/bin/python poses.py go "look at phone"     # move back to it
  .venv/bin/python poses.py list                   # show all saved poses

Names are case-insensitive; spaces and underscores are interchangeable.
Poses are exact joint configurations stored in arm_poses.json ('poses.json'
is a coworker's file with a different schema — Cartesian end-position poses
for capture_pose.py/pickup.py; don't confuse the two). 'go' is a single
coordinated joint move — stop any tracker script first (one arm commander
at a time).

From other code:
  from poses import goto_pose, save_pose
  await goto_pose(machine, "look at phone")
"""

import asyncio
import json
import sys
from pathlib import Path

from viam.components.arm import Arm
from viam.proto.component.arm import JointPositions

from robot import ARM, connect

POSES_FILE = Path(__file__).parent / "arm_poses.json"


def _key(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _load() -> dict:
    if POSES_FILE.exists():
        return json.loads(POSES_FILE.read_text())
    return {}


async def save_pose(machine, name: str) -> list[float]:
    arm = Arm.from_robot(machine, ARM)
    joints = list((await arm.get_joint_positions()).values)
    poses = _load()
    poses[_key(name)] = joints
    POSES_FILE.write_text(json.dumps(poses, indent=2))
    return joints


async def goto_pose(machine, name: str) -> None:
    poses = _load()
    key = _key(name)
    if key not in poses:
        known = ", ".join(sorted(poses)) or "(none)"
        raise RuntimeError(f"no pose named '{name}' — saved poses: {known}")
    arm = Arm.from_robot(machine, ARM)
    await arm.move_to_joint_positions(JointPositions(values=poses[key]))
    print(f"at '{key}': {[round(j, 1) for j in poses[key]]}")


async def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("save", "go", "list"):
        print(__doc__)
        sys.exit(1)
    if args[0] == "list":
        for name, joints in sorted(_load().items()):
            print(f"  {name}: {[round(j, 1) for j in joints]}")
        return
    if len(args) < 2:
        print(f"usage: poses.py {args[0]} <name>")
        sys.exit(1)
    name = " ".join(args[1:])
    machine = await connect()
    try:
        if args[0] == "save":
            joints = await save_pose(machine, name)
            print(f"saved '{_key(name)}': {[round(j, 1) for j in joints]}")
        else:
            await goto_pose(machine, name)
    finally:
        await machine.close()


if __name__ == "__main__":
    asyncio.run(main())
