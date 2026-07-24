import asyncio
import json
import os
import sys

from drk_robot import StableRobot

ARM_NAME = "arm-1"
OUTPUT_PATH = "poses.json"


async def main():
    if len(sys.argv) != 2:
        print("Usage: capture_pose.py <pose_name>")
        print("Example: capture_pose.py phone_pickup")
        sys.exit(1)
    pose_name = sys.argv[1]

    async with StableRobot.from_env() as robot:
        arm = await robot.arm(ARM_NAME)
        pose = await robot.call(lambda: arm.get_end_position(), label="get_end_position")

        recorded = {
            "x": pose.x,
            "y": pose.y,
            "z": pose.z,
            "o_x": pose.o_x,
            "o_y": pose.o_y,
            "o_z": pose.o_z,
            "theta": pose.theta,
        }

        poses = {}
        if os.path.exists(OUTPUT_PATH):
            with open(OUTPUT_PATH) as f:
                poses = json.load(f)

        poses[pose_name] = recorded
        with open(OUTPUT_PATH, "w") as f:
            json.dump(poses, f, indent=2)

        print(f"Captured '{pose_name}': {recorded}")
        print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
