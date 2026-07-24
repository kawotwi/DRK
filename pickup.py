import asyncio
import json
import sys

from drk_robot import StableRobot
from viam.services.motion import Motion
from viam.proto.common import Pose, PoseInFrame

ARM_NAME = "arm-1"
GRIPPER_NAME = "gripper-1"
POSES_PATH = "poses.json"
PREGRASP_CLEARANCE_MM = 60  # how far above the grasp pose to approach from


def load_pose(name):
    with open(POSES_PATH) as f:
        poses = json.load(f)
    p = poses[name]
    return Pose(x=p["x"], y=p["y"], z=p["z"], o_x=p["o_x"], o_y=p["o_y"], o_z=p["o_z"], theta=p["theta"])


async def move_to(robot, motion, pose, label):
    print(f"Moving to {label}: x={pose.x:.1f} y={pose.y:.1f} z={pose.z:.1f}")
    goal = PoseInFrame(reference_frame="world", pose=pose)
    success = await robot.call(
        lambda: motion.move(component_name=ARM_NAME, destination=goal), label=f"move:{label}"
    )
    print(f"  -> success={success}")
    return success


async def main():
    valid_stages = ("pregrasp", "align", "grasp", "lift", "return", "release", "full")
    if len(sys.argv) != 2 or sys.argv[1] not in valid_stages:
        print("Usage: pickup.py <pregrasp|align|grasp|lift|return|release|full>")
        print("  pregrasp  - move to a safe hover position above the taught grasp pose (no grab)")
        print("  align     - descend to the exact taught pose WITHOUT closing the gripper (visual check)")
        print("  grasp     - from pregrasp, descend to the taught pose and close the gripper")
        print("  lift      - raise back to the pregrasp hover height")
        print("  return    - descend back down to the taught pose (origin), still holding the phone")
        print("  release   - open the gripper")
        print("  full      - run pregrasp -> grasp -> lift -> return -> release in sequence")
        sys.exit(1)
    stage = sys.argv[1]

    grasp_pose = load_pose("phone_pickup")
    pregrasp_pose = Pose(
        x=grasp_pose.x, y=grasp_pose.y, z=grasp_pose.z + PREGRASP_CLEARANCE_MM,
        o_x=grasp_pose.o_x, o_y=grasp_pose.o_y, o_z=grasp_pose.o_z, theta=grasp_pose.theta,
    )

    async with StableRobot.from_env() as robot:
        arm = await robot.arm(ARM_NAME)
        gripper = await robot.gripper(GRIPPER_NAME)
        motion = Motion.from_robot(robot.machine, "builtin")

        if stage in ("pregrasp", "full"):
            await robot.call(lambda: gripper.open(), label="gripper.open")
            await move_to(robot, motion, pregrasp_pose, "pregrasp (hover)")

        if stage == "align":
            await move_to(robot, motion, grasp_pose, "exact captured pose (no grab)")

        if stage in ("grasp", "full"):
            await move_to(robot, motion, grasp_pose, "grasp pose")
            grabbed = await robot.call(lambda: gripper.grab(), label="gripper.grab")
            print(f"gripper.grab() -> {grabbed}")
            status = await robot.call(lambda: gripper.is_holding_something(), label="is_holding_something")
            print(f"is_holding_something() -> {status}")

        if stage in ("lift", "full"):
            await move_to(robot, motion, pregrasp_pose, "pregrasp (lift)")

        if stage in ("return", "full"):
            await move_to(robot, motion, grasp_pose, "origin (return, still holding)")

        if stage in ("release", "full"):
            await robot.call(lambda: gripper.open(), label="gripper.open")
            print("Gripper opened.")

        final_pose = await robot.call(lambda: arm.get_end_position(), label="get_end_position")
        print(f"Final arm pose: x={final_pose.x:.1f} y={final_pose.y:.1f} z={final_pose.z:.1f}")


if __name__ == "__main__":
    asyncio.run(main())
