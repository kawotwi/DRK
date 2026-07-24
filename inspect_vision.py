import asyncio

from drk_robot import StableRobot

CAMERA_NAME = "cam-1"
VISION_NAME = "vision-1-yolo"


async def main():
    async with StableRobot.from_env() as robot:
        vision = await robot.vision(VISION_NAME)

        detections = await robot.call(
            lambda: vision.get_detections_from_camera(CAMERA_NAME), label="get_detections"
        )
        print(f"Detections in current frame ({len(detections)}):")
        for d in detections:
            print(f"  {d.class_name}  confidence={d.confidence:.2f}  box=({d.x_min},{d.y_min})-({d.x_max},{d.y_max})")

        classifications = await robot.call(
            lambda: vision.get_classifications_from_camera(CAMERA_NAME, count=5), label="get_classifications"
        )
        print(f"\nTop classifications in current frame ({len(classifications)}):")
        for c in classifications:
            print(f"  {c.class_name}  confidence={c.confidence:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
