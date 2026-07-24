"""Shared Viam connection for DRK. Reads credentials from .env (gitignored).

Usage:
    from robot import connect
    machine = await connect()
"""

import os
from pathlib import Path

from viam.robot.client import RobotClient

ARM = "arm-1"
GRIPPER = "gripper-1"
CAMERA = "cam-1"
VISION_YOLO = "vision-1-yolo"


def _load_env() -> None:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


async def connect() -> RobotClient:
    _load_env()
    api_key = os.environ["VIAM_API_KEY"]
    api_key_id = os.environ["VIAM_API_KEY_ID"]
    address = os.environ["VIAM_ADDRESS"]
    opts = RobotClient.Options.with_api_key(api_key=api_key, api_key_id=api_key_id)
    return await RobotClient.at_address(address, opts)
