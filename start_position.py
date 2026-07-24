"""Record and return to the robot's starting position (exact joint angles).

  .venv/bin/python start_position.py save   # record CURRENT pose as starting position
  .venv/bin/python start_position.py go     # move the arm back to it

'go' is a single coordinated joint move at the arm's configured speed — exact
and repeatable, no motion planner involved. Stop any tracker script before
running 'go' (one arm commander at a time).

From other code:
  from start_position import go_start
  await go_start(machine)
"""

import asyncio
import json
import sys
from pathlib import Path

from viam.components.arm import Arm
from viam.proto.component.arm import JointPositions

from robot import ARM, connect

START_FILE = Path(__file__).parent / "starting_position.json"


async def save_start(machine) -> list[float]:
    arm = Arm.from_robot(machine, ARM)
    joints = list((await arm.get_joint_positions()).values)
    START_FILE.write_text(json.dumps({"joints_deg": joints}, indent=2))
    return joints


async def go_start(machine) -> None:
    if not START_FILE.exists():
        raise RuntimeError("no starting_position.json — run 'start_position.py save' first")
    joints = json.loads(START_FILE.read_text())["joints_deg"]
    arm = Arm.from_robot(machine, ARM)
    await arm.move_to_joint_positions(JointPositions(values=joints))
    print(f"at starting position: {[round(j, 1) for j in joints]}")


async def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd not in ("save", "go"):
        print(__doc__)
        sys.exit(1)
    machine = await connect()
    try:
        if cmd == "save":
            joints = await save_start(machine)
            print(f"starting position saved: {[round(j, 1) for j in joints]}")
        else:
            await go_start(machine)
    finally:
        await machine.close()


if __name__ == "__main__":
    asyncio.run(main())
