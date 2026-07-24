# Viam Python SDK Cheatsheet

Quick-reference tables, templates, and common patterns. For detailed docs, see
`python-sdk-reference.md`.

---

## Import Paths

### Components

| Component | Import | API String |
|---|---|---|
| Arm | `from viam.components.arm import Arm` | `rdk:component:arm` |
| Base | `from viam.components.base import Base` | `rdk:component:base` |
| Board | `from viam.components.board import Board` | `rdk:component:board` |
| Button | `from viam.components.button import Button` | `rdk:component:button` |
| Camera | `from viam.components.camera import Camera` | `rdk:component:camera` |
| Encoder | `from viam.components.encoder import Encoder` | `rdk:component:encoder` |
| Gantry | `from viam.components.gantry import Gantry` | `rdk:component:gantry` |
| Generic | `from viam.components.generic import Generic` | `rdk:component:generic` |
| Gripper | `from viam.components.gripper import Gripper` | `rdk:component:gripper` |
| Input Controller | `from viam.components.input import Controller` | `rdk:component:input_controller` |
| Motor | `from viam.components.motor import Motor` | `rdk:component:motor` |
| Movement Sensor | `from viam.components.movement_sensor import MovementSensor` | `rdk:component:movement_sensor` |
| Pose Tracker | `from viam.components.pose_tracker import PoseTracker` | `rdk:component:pose_tracker` |
| Power Sensor | `from viam.components.power_sensor import PowerSensor` | `rdk:component:power_sensor` |
| Sensor | `from viam.components.sensor import Sensor` | `rdk:component:sensor` |
| Servo | `from viam.components.servo import Servo` | `rdk:component:servo` |
| Switch | `from viam.components.switch import Switch` | `rdk:component:switch` |
| Audio In | `from viam.components.audio_in import AudioIn` | `rdk:component:audio_in` |
| Audio Out | `from viam.components.audio_out import AudioOut` | `rdk:component:audio_out` |

### Services

| Service | Import | API String |
|---|---|---|
| Vision | `from viam.services.vision import Vision` | `rdk:service:vision` |
| Motion | `from viam.services.motion import Motion` | `rdk:service:motion` |
| SLAM | `from viam.services.slam import SLAM` | `rdk:service:slam` |
| Navigation | `from viam.services.navigation import Navigation` | `rdk:service:navigation` |
| MLModel | `from viam.services.mlmodel import MLModel` | `rdk:service:mlmodel` |
| Discovery | `from viam.services.discovery import Discovery` | `rdk:service:discovery` |
| WorldStateStore | `from viam.services.worldstatestore import WorldStateStore` | `rdk:service:world_state_store` |
| Generic | `from viam.services.generic import Generic` | `rdk:service:generic` |

### Common Types

| Type | Import |
|---|---|
| Pose | `from viam.proto.common import Pose` |
| PoseInFrame | `from viam.proto.common import PoseInFrame` |
| Vector3 | `from viam.proto.common import Vector3` |
| GeoPoint | `from viam.proto.common import GeoPoint` |
| Orientation | `from viam.proto.common import Orientation` |
| Geometry | `from viam.proto.common import Geometry` |
| WorldState | `from viam.proto.common import WorldState` |
| Transform | `from viam.proto.common import Transform` |
| ResourceName | `from viam.proto.common import ResourceName` |
| JointPositions | `from viam.proto.component.arm import JointPositions` |
| Detection | `from viam.proto.service.vision import Detection` |
| Classification | `from viam.proto.service.vision import Classification` |
| PointCloudObject | `from viam.proto.common import PointCloudObject` |
| Constraints | `from viam.proto.service.motion import Constraints` |
| MotionConfiguration | `from viam.proto.service.motion import MotionConfiguration` |
| Metadata (ML) | `from viam.proto.service.mlmodel import Metadata` |
| ComponentConfig | `from viam.proto.app.robot import ComponentConfig` |

### Module Development

| Purpose | Import |
|---|---|
| Module class | `from viam.module.module import Module` |
| EasyResource mixin | `from viam.resource.easy_resource import EasyResource` |
| stub_model decorator | `from viam.resource.easy_resource import stub_model` |
| Registry | `from viam.resource.registry import Registry, ResourceCreatorRegistration` |
| API / Model types | `from viam.resource.types import API, Model, ModelFamily` |
| ResourceBase | `from viam.resource.base import ResourceBase` |
| Reconfigurable | `from viam.module.types import Reconfigurable` |
| Stoppable | `from viam.module.types import Stoppable` |
| Logging | `from viam.logging import getLogger` |

### Media / Image

| Purpose | Import |
|---|---|
| ViamImage | `from viam.media.video import ViamImage` |
| NamedImage | `from viam.media.video import NamedImage` |
| CameraMimeType | `from viam.media.video import CameraMimeType` |

---

## Async Connection Boilerplate

### Minimal Client Script

```python
import asyncio
from viam.robot.client import RobotClient
from viam.components.sensor import Sensor


async def main():
    opts = RobotClient.Options.with_api_key(
        api_key='YOUR_API_KEY',
        api_key_id='YOUR_API_KEY_ID'
    )
    robot = await RobotClient.at_address('YOUR_ROBOT_ADDRESS', opts)
    try:
        sensor = Sensor.from_robot(robot, "my_sensor")
        readings = await sensor.get_readings()
        print(readings)
    finally:
        await robot.close()


if __name__ == "__main__":
    asyncio.run(main())
```

### Context Manager Client

```python
import asyncio
from viam.robot.client import RobotClient
from viam.components.arm import Arm
from viam.proto.common import Pose


async def main():
    opts = RobotClient.Options.with_api_key(
        api_key='YOUR_API_KEY',
        api_key_id='YOUR_API_KEY_ID'
    )
    robot = await RobotClient.at_address('YOUR_ROBOT_ADDRESS', opts)
    async with robot:
        arm = Arm.from_robot(robot, "my_arm")
        pos = await arm.get_end_position()
        print(f"Arm position: x={pos.x}, y={pos.y}, z={pos.z}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Method Signature Quick Reference

### Arm

| Method | Returns |
|---|---|
| `await arm.get_end_position()` | `Pose` |
| `await arm.move_to_position(pose)` | `None` |
| `await arm.move_to_joint_positions(positions)` | `None` |
| `await arm.get_joint_positions()` | `JointPositions` |
| `await arm.stop()` | `None` |
| `await arm.is_moving()` | `bool` |
| `await arm.get_kinematics()` | `Tuple[KinematicsFileFormat, bytes]` |

### Base

| Method | Returns |
|---|---|
| `await base.move_straight(distance_mm, velocity_mm_s)` | `None` |
| `await base.spin(angle_deg, velocity_deg_s)` | `None` |
| `await base.set_power(linear: Vector3, angular: Vector3)` | `None` |
| `await base.set_velocity(linear: Vector3, angular: Vector3)` | `None` |
| `await base.stop()` | `None` |
| `await base.is_moving()` | `bool` |
| `await base.get_properties()` | `Base.Properties` |

### Camera

| Method | Returns |
|---|---|
| `await camera.get_images()` | `Tuple[Seq[NamedImage], ResponseMetadata]` |
| `await camera.get_point_cloud()` | `Tuple[bytes, str]` |
| `await camera.get_properties()` | `Camera.Properties` |

### Motor

| Method | Returns |
|---|---|
| `await motor.set_power(power)` | `None` |
| `await motor.go_for(rpm, revolutions)` | `None` |
| `await motor.go_to(rpm, position_revolutions)` | `None` |
| `await motor.set_rpm(rpm)` | `None` |
| `await motor.reset_zero_position(offset)` | `None` |
| `await motor.get_position()` | `float` (revolutions) |
| `await motor.get_properties()` | `Motor.Properties` |
| `await motor.stop()` | `None` |
| `await motor.is_powered()` | `Tuple[bool, float]` |
| `await motor.is_moving()` | `bool` |

### Sensor

| Method | Returns |
|---|---|
| `await sensor.get_readings()` | `Mapping[str, SensorReading]` |

### Vision

| Method | Returns |
|---|---|
| `await vision.capture_all_from_camera(cam, ...)` | `CaptureAllResult` |
| `await vision.get_detections_from_camera(cam)` | `List[Detection]` |
| `await vision.get_detections(image)` | `List[Detection]` |
| `await vision.get_classifications_from_camera(cam, count)` | `List[Classification]` |
| `await vision.get_classifications(image, count)` | `List[Classification]` |
| `await vision.get_object_point_clouds(cam)` | `List[PointCloudObject]` |

### Motion

| Method | Returns |
|---|---|
| `await motion.move(component, destination, ...)` | `bool` |
| `await motion.move_on_globe(component, dest, sensor, ...)` | `str` (execution_id) |
| `await motion.move_on_map(component, dest, slam, ...)` | `str` (execution_id) |
| `await motion.stop_plan(component)` | `None` |
| `await motion.get_plan(component)` | `GetPlanResponse` |
| `await motion.list_plan_statuses()` | `Seq[PlanStatusWithID]` |
| `await motion.get_pose(component, dest_frame)` | `PoseInFrame` |

---

## Common Type Constructions

```python
from viam.proto.common import Pose, PoseInFrame, Vector3, GeoPoint, WorldState

# Pose: position (mm) + orientation vector + theta (degrees)
pose = Pose(x=100, y=0, z=300, o_x=0, o_y=0, o_z=1, theta=0)

# PoseInFrame: pose + frame name
pif = PoseInFrame(reference_frame="world", pose=pose)

# Vector3
v = Vector3(x=0, y=50, z=0)  # e.g., 50 mm/s forward for base

# GeoPoint
gp = GeoPoint(latitude=40.7128, longitude=-74.0060)

# JointPositions (values in degrees)
from viam.proto.component.arm import JointPositions
jp = JointPositions(values=[0.0, 45.0, 90.0, 0.0, 0.0, 0.0])
```

---

## Image Conversions

### ViamImage -> NumPy array (via PIL)

```python
from PIL import Image
import numpy as np
import io

images, _ = await camera.get_images()
img = images[0]
pil = Image.open(io.BytesIO(img.data))
arr = np.array(pil)  # shape: (H, W, C) in RGB
```

### ViamImage -> OpenCV (BGR)

```python
import cv2
import numpy as np
from PIL import Image
import io

images, _ = await camera.get_images()
img = images[0]
pil = Image.open(io.BytesIO(img.data))
rgb = np.array(pil)
bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
```

### NumPy/OpenCV -> ViamImage

```python
from viam.media.video import ViamImage, CameraMimeType
import cv2

_, jpeg_bytes = cv2.imencode('.jpg', bgr_image)
viam_img = ViamImage(jpeg_bytes.tobytes(), CameraMimeType.JPEG)
```

### Depth Image -> NumPy

```python
from viam.media.video import CameraMimeType
import numpy as np

images, _ = await camera.get_images()
for img in images:
    if img.mime_type == CameraMimeType.VIAM_RAW_DEPTH:
        depth_2d = img.bytes_to_depth_array()  # List[List[int]]
        depth_np = np.array(depth_2d, dtype=np.uint16)
```

### Point Cloud -> NumPy (via Open3D)

```python
import open3d as o3d
import numpy as np

data, _ = await camera.get_point_cloud()
with open("/tmp/pc.pcd", "wb") as f:
    f.write(data)
pcd = o3d.io.read_point_cloud("/tmp/pc.pcd")
points = np.asarray(pcd.points)  # shape: (N, 3)
```

---

## Module Server Templates

### Minimal Module (EasyResource)

```python
#!/usr/bin/env python3
import asyncio
from viam.components.sensor import Sensor
from viam.resource.easy_resource import EasyResource
from viam.module.module import Module


class MySensor(Sensor, EasyResource):
    MODEL = "my-org:my-family:my-sensor"

    async def get_readings(self, **kwargs):
        return {"temperature": 22.5, "humidity": 45.0}


if __name__ == '__main__':
    asyncio.run(Module.run_from_registry())
```

### Module with Reconfigure and Validation

```python
#!/usr/bin/env python3
import asyncio
from typing import ClassVar, Mapping, Optional, Sequence, Tuple

from typing_extensions import Self

from viam.components.sensor import Sensor
from viam.module.module import Module
from viam.module.types import Reconfigurable
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model
from viam.utils import SensorReading


class TemperatureSensor(Sensor, EasyResource, Reconfigurable):
    MODEL = "my-org:sensors:temperature"

    offset: float = 0.0

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        # EasyResource.new() does not call reconfigure(); override to apply config on construction
        sensor = cls(config.name)
        sensor.reconfigure(config, dependencies)
        return sensor

    @classmethod
    def validate_config(cls, config: ComponentConfig) -> Tuple[Sequence[str], Sequence[str]]:
        if "offset" in config.attributes.fields:
            val = config.attributes.fields["offset"]
            if not val.HasField("number_value"):
                raise ValueError("offset must be a number")
        return [], []

    def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        if "offset" in config.attributes.fields:
            self.offset = config.attributes.fields["offset"].number_value

    async def get_readings(self, **kwargs) -> Mapping[str, SensorReading]:
        raw = 22.5  # replace with actual reading
        return {"temperature_c": raw + self.offset}


if __name__ == '__main__':
    asyncio.run(Module.run_from_registry())
```

### Module with Dependencies

```python
#!/usr/bin/env python3
import asyncio
from typing import Mapping, Sequence, Tuple

from typing_extensions import Self

from viam.components.camera import Camera
from viam.components.sensor import Sensor
from viam.module.module import Module
from viam.module.types import Reconfigurable
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.easy_resource import EasyResource
from viam.utils import SensorReading


class BrightnessSensor(Sensor, EasyResource, Reconfigurable):
    MODEL = "my-org:vision:brightness"
    camera: Camera = None

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        sensor = cls(config.name)
        sensor.reconfigure(config, dependencies)
        return sensor

    @classmethod
    def validate_config(cls, config: ComponentConfig) -> Tuple[Sequence[str], Sequence[str]]:
        camera_name = config.attributes.fields.get("camera_name")
        if camera_name:
            # Return camera as a required dependency
            return [camera_name.string_value], []
        return [], []

    def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        for rn, dep in dependencies.items():
            if rn.subtype == "camera":
                self.camera = dep

    async def get_readings(self, **kwargs) -> Mapping[str, SensorReading]:
        if self.camera is None:
            return {"brightness": 0.0}
        images, _ = await self.camera.get_images()
        # compute brightness from image...
        return {"brightness": 128.0}


if __name__ == '__main__':
    asyncio.run(Module.run_from_registry())
```

### Manual Registration (Advanced)

```python
#!/usr/bin/env python3
import asyncio
from typing import ClassVar, Mapping, Sequence, Tuple

from typing_extensions import Self

from viam.components.motor import Motor
from viam.module.module import Module
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.registry import Registry, ResourceCreatorRegistration
from viam.resource.types import Model, ModelFamily


class MyMotor(Motor):
    MODEL: ClassVar[Model] = Model(ModelFamily("my-org", "motors"), "my-motor")

    def __init__(self, name: str):
        super().__init__(name)
        self._power = 0.0
        self._position = 0.0

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        return cls(config.name)

    @classmethod
    def validate_config(cls, config: ComponentConfig) -> Tuple[Sequence[str], Sequence[str]]:
        return [], []

    async def set_power(self, power, **kwargs):
        self._power = power

    async def go_for(self, rpm, revolutions, **kwargs):
        pass

    async def go_to(self, rpm, position_revolutions, **kwargs):
        pass

    async def set_rpm(self, rpm, **kwargs):
        pass

    async def reset_zero_position(self, offset, **kwargs):
        self._position = 0.0

    async def get_position(self, **kwargs) -> float:
        return self._position

    async def get_properties(self, **kwargs) -> Motor.Properties:
        return Motor.Properties(position_reporting=True)

    async def stop(self, **kwargs):
        self._power = 0.0

    async def is_powered(self, **kwargs):
        return (self._power != 0.0, self._power)

    async def is_moving(self) -> bool:
        return self._power != 0.0


async def main():
    Registry.register_resource_creator(
        Motor.API,
        MyMotor.MODEL,
        ResourceCreatorRegistration(MyMotor.new, MyMotor.validate_config)
    )
    module = Module.from_args()
    module.add_model_from_registry(Motor.API, MyMotor.MODEL)
    await module.start()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Units Reference

| Measurement | Unit | Notes |
|---|---|---|
| Position (Pose x, y, z) | mm | Millimeters |
| Orientation (Pose theta) | degrees | |
| Orientation vector (o_x, o_y, o_z) | unit vector | Rotation axis |
| JointPositions values | degrees | Go SDK uses radians internally |
| Base.move_straight distance | mm | |
| Base.move_straight velocity | mm/s | |
| Base.spin angle | degrees | |
| Base.spin velocity | deg/s | |
| Base.set_velocity linear | mm/s (Vector3) | |
| Base.set_velocity angular | deg/s (Vector3) | |
| Motor power | [-1, 1] | Fractional |
| Motor position | revolutions | From zero |
| Motor RPM | rev/min | |
| Gantry positions | mm | |
| Gantry speeds | mm/s | |
| Servo angle | degrees | |
| GeoPoint | latitude, longitude | Decimal degrees |
| Altitude (MovementSensor) | meters | |
| Linear velocity | m/s | Vector3 |
| Angular velocity | deg/s | Vector3 |
| Linear acceleration | m/s^2 | Vector3 |
| Compass heading | degrees | 0-360 |
| Timeout | seconds | float |

---

## Common Errors and Fixes

| Error | Cause | Fix |
|---|---|---|
| `RuntimeWarning: coroutine was never awaited` | Forgot `await` on an async call | Add `await` before the call |
| `ConnectionError: Unable to establish a connection` | Wrong address, robot offline, or bad credentials | Check address format, verify API key |
| `ResourceNotFoundError` | Component/service name mismatch | Check `robot.resource_names` for available resources |
| `GRPCError: UNAVAILABLE` | Connection dropped mid-call | Ensure `check_connection_interval > 0` in Options |
| `NotImplementedError` on `do_command` | Component doesn't override `do_command` | Override in your module class, or use a component-specific method |
| `ValidationError` in module | `validate_config` raised or returned wrong type | Return `Tuple[Sequence[str], Sequence[str]]` |
| `TypeError: missing MODEL field` | EasyResource subclass missing MODEL | Add `MODEL = "org:family:name"` class attribute |
| `DuplicateResourceError` | Model registered twice | Ensure single registration per API/model pair |
| Module never becomes ready | Exception in `new()` or `reconfigure()` | Check module logs, ensure config attributes exist |
| `MethodNotImplementedError` | Used `@stub_model` and called unimplemented method | Implement the abstract method |
| `AttributeError: 'NoneType'` on dependency | Dependency not available at configure time | Check `validate_config` returns correct dependency names |
| Images look wrong colors in OpenCV | RGB vs BGR mismatch | Use `cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)` |
| `ValueError: not a valid Model` | Model string not in `org:family:name` format | Use three colon-separated segments |

---

## Go SDK vs Python SDK Quick Comparison

| Aspect | Go SDK | Python SDK |
|---|---|---|
| Connection | `client.New(ctx, addr, logger, opts)` | `await RobotClient.at_address(addr, opts)` |
| Get component | `arm.FromRobot(robot, "name")` | `Arm.from_robot(robot, "name")` |
| Method style | `arm.EndPosition(ctx, extra)` | `await arm.get_end_position(extra=...)` |
| Naming | CamelCase | snake_case |
| Concurrency | goroutines / `context.Context` | asyncio / `timeout` kwarg |
| Error handling | `(result, error)` returns | Exceptions |
| Joint angles | Radians internally | Degrees (in `JointPositions.values`) |
| Types | Go structs (`spatialmath.Pose`) | Protobuf messages (`viam.proto.common.Pose`) |
| Module entry | `module.NewModule(ctx)` + manual registration | `Module.run_from_registry()` or manual |
| Module lifecycle | `AddResource`/`Reconfigure`/`RemoveResource` | `new()`/`reconfigure()`/`close()` |
| Pose construction | `spatialmath.NewPoseFromPoint(r3.Vector{...})` | `Pose(x=..., y=..., z=...)` |
