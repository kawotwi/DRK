import asyncio

from drk_robot import StableRobot

ARM_NAME = "arm-1"


async def main():
    async with StableRobot.from_env() as robot:
        arm = await robot.arm(ARM_NAME)

        pos = await robot.call(lambda: arm.get_end_position(), label="get_end_position")
        print(f"get_end_position() -> x={pos.x:.1f} y={pos.y:.1f} z={pos.z:.1f} "
              f"o_x={pos.o_x:.3f} o_y={pos.o_y:.3f} o_z={pos.o_z:.3f} theta={pos.theta:.2f}")

        moving = await robot.call(lambda: arm.is_moving(), label="is_moving")
        print(f"is_moving() -> {moving}")

        joints = await robot.call(lambda: arm.get_joint_positions(), label="get_joint_positions")
        print(f"get_joint_positions() -> {joints.values}")


if __name__ == "__main__":
    asyncio.run(main())
