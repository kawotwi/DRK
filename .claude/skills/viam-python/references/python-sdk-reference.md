# Viam Python SDK Reference

> Built from `viam-python-sdk` source circa April 2026. The SDK evolves — verify
> against the user's installed version (`pip show viam-sdk`) and the official docs
> at `python.viam.dev`. Never fabricate signatures; acknowledge gaps.

---

## SDK Architecture

### Overview

The Viam Python SDK is an **async-first** gRPC client library. All robot
interactions use `asyncio`. The SDK provides:

- **Client classes** for every component and service — used when connecting to a
  remote machine from a Python script.
- **Base classes** for building custom modules — extend these to create new
  component/service implementations that run as separate processes alongside
  `viam-server`.
- **Protobuf bindings** under `viam.proto.*` — generated from the Viam API
  protobuf definitions.
- **Media helpers** for images (`ViamImage`, `CameraMimeType`) and audio.

### Connection Lifecycle

```
RobotClient.at_address(addr, opts)
    │
    ├─ dial() → gRPC channel (WebRTC or direct)
    ├─ refresh() → discover available resources
    ├─ (optional) periodic refresh task
    └─ (optional) connection-check / reconnect task

... use resources ...

robot.close()  → cancel tasks, close channel
```

Every resource is obtained from the robot via `Component.from_robot(robot, name)`
or `Service.from_robot(robot, name)`. These return typed client stubs.

### Key Modules

| Module | Purpose |
|---|---|
| `viam.robot.client` | `RobotClient` — main entry point |
| `viam.components.*` | Component interfaces and clients |
| `viam.services.*` | Service interfaces and clients |
| `viam.module.module` | `Module` class for building modules |
| `viam.resource.base` | `ResourceBase` protocol |
| `viam.resource.types` | `API`, `Model`, `ModelFamily`, `ResourceName` |
| `viam.resource.registry` | `Registry` for model registration |
| `viam.resource.easy_resource` | `EasyResource` mixin for simpler modules |
| `viam.proto.common` | Shared protobuf types (Pose, PoseInFrame, etc.) |
| `viam.media.video` | `ViamImage`, `CameraMimeType`, `NamedImage` |
| `viam.rpc.dial` | `DialOptions`, `Credentials`, `dial()` |
| `viam.utils` | `ValueTypes`, `SensorReading`, conversion helpers |
| `viam.logging` | SDK logging utilities |

---

## RobotClient

**Import:** `from viam.robot.client import RobotClient`

### Connection Methods

```python
# Primary: connect with API key
opts = RobotClient.Options.with_api_key(
    api_key='<API-KEY>',
    api_key_id='<API-KEY-ID>'
)
robot = await RobotClient.at_address('<ADDRESS>', opts)

# Alternative: connect with existing channel
robot = await RobotClient.with_channel(channel, opts)
```

### RobotClient.Options

```python
@dataclass
class Options:
    refresh_interval: int = 0               # seconds, 0 = no auto-refresh
    dial_options: Optional[DialOptions] = None
    log_level: int = logging.INFO
    check_connection_interval: int = 10     # seconds, 0 = no check
    attempt_reconnect_interval: int = 1     # seconds, 0 = no reconnect
    disable_sessions: bool = False

    @classmethod
    def with_api_key(cls, api_key: str, api_key_id: str, **kwargs) -> Self: ...
```

### Key Methods

```python
robot.resource_names -> List[ResourceName]   # list all resources
robot.get_component(ResourceName) -> ComponentBase
robot.get_service(ResourceName) -> ServiceBase
await robot.refresh()                         # manually refresh resources
await robot.close()                           # close connection, cancel tasks
await robot.stop_all(extra={})                # emergency stop all actuators

# Frame system
await robot.get_frame_system_config(additional_transforms=None) -> List[FrameSystemConfig]
await robot.transform_pose(query: PoseInFrame, destination: str, additional_transforms=None) -> PoseInFrame

# Operations
await robot.get_operations() -> List[Operation]
await robot.cancel_operation(id: str)
await robot.block_for_operation(id: str)

# Metadata
await robot.get_cloud_metadata() -> GetCloudMetadataResponse
await robot.get_version() -> GetVersionResponse
await robot.get_machine_status() -> GetMachineStatusResponse
await robot.get_models_from_modules() -> List[ModuleModel]
await robot.shutdown()
await robot.restart_module(id=None, name=None)
```

### Context Manager

```python
async with await RobotClient.at_address(addr, opts) as robot:
    # robot auto-closes when exiting the block
    arm = Arm.from_robot(robot, "my_arm")
    pos = await arm.get_end_position()
# Connection closed here
```

**Note:** Robots created with `at_address` auto-close in the context manager.
Robots created with `with_channel` do NOT auto-close the channel.

---

## Component Interfaces

All components inherit from `ComponentBase` and share these base methods:

```python
# Get from robot (all components)
component = Component.from_robot(robot, "name") -> Self
component.get_resource_name("name") -> ResourceName

# Common methods on all components
await component.do_command({"cmd": "val"}) -> Mapping[str, ValueTypes]
await component.get_status() -> Mapping[str, ValueTypes]
await component.get_geometries() -> Sequence[Geometry]
await component.close()
```

### Arm

**Import:** `from viam.components.arm import Arm`
**Types:** `from viam.proto.common import Pose` and `from viam.proto.component.arm import JointPositions`
**API:** `rdk:component:arm`

```python
arm = Arm.from_robot(robot, "my_arm")

await arm.get_end_position(*, extra=None, timeout=None) -> Pose
await arm.move_to_position(pose: Pose, *, extra=None, timeout=None)
await arm.move_to_joint_positions(positions: JointPositions, *, extra=None, timeout=None)
await arm.get_joint_positions(*, extra=None, timeout=None) -> JointPositions
await arm.stop(*, extra=None, timeout=None)
await arm.is_moving() -> bool
await arm.get_kinematics(*, extra=None, timeout=None) -> KinematicsReturn
    # KinematicsReturn = Union[
    #     Tuple[KinematicsFileFormat.ValueType, bytes],
    #     Tuple[KinematicsFileFormat.ValueType, bytes, Mapping[str, Mesh]]
    # ]
```

### Base

**Import:** `from viam.components.base import Base`
**Types:** `from viam.proto.common import Vector3`
**API:** `rdk:component:base`

```python
base = Base.from_robot(robot, "my_base")

await base.move_straight(distance: int, velocity: float, *, extra=None, timeout=None)
    # distance in mm, velocity in mm/s. Negative = backward.
await base.spin(angle: float, velocity: float, *, extra=None, timeout=None)
    # angle in degrees, velocity in deg/s. Positive angle + positive velocity = turn left.
await base.set_power(linear: Vector3, angular: Vector3, *, extra=None, timeout=None)
    # linear.y = forward power [-1,1], angular.z = turn power [-1,1]
await base.set_velocity(linear: Vector3, angular: Vector3, *, extra=None, timeout=None)
    # linear in mm/s, angular in deg/s
await base.stop(*, extra=None, timeout=None)
await base.is_moving() -> bool
await base.get_properties(*, timeout=None) -> Base.Properties
    # Properties: width_meters, turning_radius_meters, wheel_circumference_meters
```

### Board

**Import:** `from viam.components.board import Board`
**API:** `rdk:component:board`

```python
board = Board.from_robot(robot, "my_board")

# Sub-resources
analog = await board.analog_by_name(name: str) -> Board.Analog
interrupt = await board.digital_interrupt_by_name(name: str) -> Board.DigitalInterrupt
pin = await board.gpio_pin_by_name(name: str) -> Board.GPIOPin

# Board methods
await board.set_power_mode(mode: PowerMode.ValueType, duration: Optional[timedelta] = None, *, extra=None, timeout=None)
await board.stream_ticks(interrupts: List[Board.DigitalInterrupt], *, timeout=None) -> TickStream

# Board.Analog
await analog.read(*, extra=None, timeout=None) -> Board.Analog.Value  # ReadAnalogReaderResponse
await analog.write(value: int, *, extra=None, timeout=None)

# Board.DigitalInterrupt
await interrupt.value(*, extra=None, timeout=None) -> int

# Board.GPIOPin
await pin.set(high: bool, *, extra=None, timeout=None)
await pin.get(*, extra=None, timeout=None) -> bool
await pin.get_pwm(*, extra=None, timeout=None) -> float
await pin.set_pwm(duty_cycle: float, *, extra=None, timeout=None)
await pin.get_pwm_frequency(*, extra=None, timeout=None) -> int
await pin.set_pwm_frequency(frequency: int, *, extra=None, timeout=None)
```

### Camera

**Import:** `from viam.components.camera import Camera`
**Types:** `from viam.media.video import ViamImage, NamedImage, CameraMimeType`
**API:** `rdk:component:camera`

```python
camera = Camera.from_robot(robot, "my_camera")

await camera.get_images(*, filter_source_names=None, extra=None, timeout=None)
    -> Tuple[Sequence[NamedImage], ResponseMetadata]
await camera.get_point_cloud(*, extra=None, timeout=None) -> Tuple[bytes, str]
    # Returns (pcd_bytes, mime_type)
await camera.get_properties(*, timeout=None) -> Camera.Properties
    # Properties = GetPropertiesResponse (intrinsics, distortion, mime_types, extrinsics)
```

### Motor

**Import:** `from viam.components.motor import Motor`
**API:** `rdk:component:motor`

```python
motor = Motor.from_robot(robot, "my_motor")

await motor.set_power(power: float, *, extra=None, timeout=None)
    # power in [-1, 1]
await motor.go_for(rpm: float, revolutions: float, *, extra=None, timeout=None)
await motor.go_to(rpm: float, position_revolutions: float, *, extra=None, timeout=None)
await motor.set_rpm(rpm: float, *, extra=None, timeout=None)
await motor.reset_zero_position(offset: float, *, extra=None, timeout=None)
await motor.get_position(*, extra=None, timeout=None) -> float
    # revolutions from zero
await motor.get_properties(*, extra=None, timeout=None) -> Motor.Properties
    # Properties: position_reporting: bool
await motor.stop(*, extra=None, timeout=None)
await motor.is_powered(*, extra=None, timeout=None) -> Tuple[bool, float]
    # (is_powered, power_pct)
await motor.is_moving() -> bool
```

### Sensor

**Import:** `from viam.components.sensor import Sensor`
**API:** `rdk:component:sensor`

```python
sensor = Sensor.from_robot(robot, "my_sensor")

await sensor.get_readings(*, extra=None, timeout=None) -> Mapping[str, SensorReading]
    # SensorReading = Union[ValueTypes, Vector3, GeoPoint, Orientation]
```

### Movement Sensor

**Import:** `from viam.components.movement_sensor import MovementSensor`
**Types:** `from viam.proto.common import GeoPoint, Vector3, Orientation`
**API:** `rdk:component:movement_sensor`

```python
ms = MovementSensor.from_robot(robot, "my_movement_sensor")

await ms.get_position(*, extra=None, timeout=None) -> Tuple[GeoPoint, float]
    # (lat/lng, altitude_m)
await ms.get_linear_velocity(*, extra=None, timeout=None) -> Vector3  # m/s
await ms.get_angular_velocity(*, extra=None, timeout=None) -> Vector3  # deg/s
await ms.get_linear_acceleration(*, extra=None, timeout=None) -> Vector3  # m/s^2
await ms.get_compass_heading(*, extra=None, timeout=None) -> float  # degrees
await ms.get_orientation(*, extra=None, timeout=None) -> Orientation
await ms.get_properties(*, extra=None, timeout=None) -> MovementSensor.Properties
    # Properties: linear_acceleration_supported, angular_velocity_supported,
    #   orientation_supported, position_supported, compass_heading_supported,
    #   linear_velocity_supported
await ms.get_accuracy(*, extra=None, timeout=None) -> MovementSensor.Accuracy
await ms.get_readings(*, extra=None, timeout=None) -> Mapping[str, SensorReading]
```

### Servo

**Import:** `from viam.components.servo import Servo`
**API:** `rdk:component:servo`

```python
servo = Servo.from_robot(robot, "my_servo")

await servo.move(angle: int, *, extra=None, timeout=None)
await servo.get_position(*, extra=None, timeout=None) -> int  # degrees
await servo.stop(*, extra=None, timeout=None)
await servo.is_moving() -> bool
```

### Gripper

**Import:** `from viam.components.gripper import Gripper`
**API:** `rdk:component:gripper`

```python
gripper = Gripper.from_robot(robot, "my_gripper")

await gripper.open(*, extra=None, timeout=None)
await gripper.grab(*, extra=None, timeout=None) -> bool  # True if grabbed something
await gripper.is_holding_something(*, extra=None, timeout=None) -> Gripper.HoldingStatus
    # HoldingStatus: is_holding_something: bool, meta: Optional[Dict]
await gripper.stop(*, extra=None, timeout=None)
await gripper.is_moving() -> bool
await gripper.get_kinematics(*, extra=None, timeout=None) -> KinematicsReturn
```

### Encoder

**Import:** `from viam.components.encoder import Encoder`
**Types:** `from viam.proto.component.encoder import PositionType`
**API:** `rdk:component:encoder`

```python
encoder = Encoder.from_robot(robot, "my_encoder")

await encoder.get_position(position_type=None, *, extra=None, timeout=None)
    -> Tuple[float, PositionType.ValueType]
    # PositionType.POSITION_TYPE_TICKS_COUNT or PositionType.POSITION_TYPE_ANGLE_DEGREES
await encoder.reset_position(*, extra=None, timeout=None)
await encoder.get_properties(*, extra=None, timeout=None) -> Encoder.Properties
    # Properties: ticks_count_supported: bool, angle_degrees_supported: bool
```

### Gantry

**Import:** `from viam.components.gantry import Gantry`
**API:** `rdk:component:gantry`

```python
gantry = Gantry.from_robot(robot, "my_gantry")

await gantry.get_position(*, extra=None, timeout=None) -> List[float]  # mm
await gantry.move_to_position(positions: List[float], speeds: List[float], *, extra=None, timeout=None)
    # positions in mm, speeds in mm/s
await gantry.home(*, extra=None, timeout=None) -> bool
await gantry.get_lengths(*, extra=None, timeout=None) -> List[float]  # mm
await gantry.stop(*, extra=None, timeout=None)
await gantry.is_moving() -> bool
await gantry.get_kinematics(*, extra=None, timeout=None) -> KinematicsReturn
```

### Input Controller

**Import:** `from viam.components.input import Controller, Control, EventType, Event`
**API:** `rdk:component:input_controller`

```python
controller = Controller.from_robot(robot, "my_controller")

await controller.get_controls(*, extra=None, timeout=None) -> List[Control]
await controller.get_events(*, extra=None, timeout=None) -> Dict[Control, Event]
controller.register_control_callback(
    control: Control,
    triggers: List[EventType],
    function: Optional[ControlFunction],
    *, extra=None
)
await controller.trigger_event(event: Event, *, extra=None, timeout=None)
    # Raises NotSupportedError by default
```

**Event types:** `ALL_EVENTS`, `CONNECT`, `DISCONNECT`, `BUTTON_PRESS`,
`BUTTON_RELEASE`, `BUTTON_HOLD`, `BUTTON_CHANGE`, `POSITION_CHANGE_ABSOLUTE`,
`POSITION_CHANGE_RELATIVE`

**Controls:** `ABSOLUTE_X/Y/Z`, `ABSOLUTE_RX/RY/RZ`, `ABSOLUTE_HAT0_X/Y`,
`BUTTON_SOUTH/EAST/WEST/NORTH`, `BUTTON_LT/RT/LT2/RT2`, `BUTTON_L_THUMB/R_THUMB`,
`BUTTON_SELECT/START/MENU/RECORD/E_STOP`, `ABSOLUTE_PEDAL_ACCELERATOR/BRAKE/CLUTCH`

### Power Sensor

**Import:** `from viam.components.power_sensor import PowerSensor`
**API:** `rdk:component:power_sensor`

```python
ps = PowerSensor.from_robot(robot, "my_power_sensor")

await ps.get_voltage(*, extra=None, timeout=None) -> Tuple[float, bool]
    # (volts, is_ac)
await ps.get_current(*, extra=None, timeout=None) -> Tuple[float, bool]
    # (amps, is_ac)
await ps.get_power(*, extra=None, timeout=None) -> float  # watts
await ps.get_readings(*, extra=None, timeout=None) -> Mapping[str, SensorReading]
```

### Generic Component

**Import:** `from viam.components.generic import Generic`
**API:** `rdk:component:generic`

Only has `do_command()` from `ComponentBase`. No additional methods.

### Button

**Import:** `from viam.components.button import Button`
**API:** `rdk:component:button`

```python
button = Button.from_robot(robot, "my_button")

await button.push(*, extra=None, timeout=None) -> None
```

### Switch

**Import:** `from viam.components.switch import Switch`
**API:** `rdk:component:switch`

```python
switch = Switch.from_robot(robot, "my_switch")

await switch.get_position(*, extra=None, timeout=None) -> int
await switch.set_position(position: int, *, extra=None, timeout=None) -> None
await switch.get_number_of_positions(*, extra=None, timeout=None) -> Tuple[int, Sequence[str]]
    # (num_positions, labels)
```

### Pose Tracker

**Import:** `from viam.components.pose_tracker import PoseTracker`
**API:** `rdk:component:pose_tracker`

```python
pt = PoseTracker.from_robot(robot, "my_pose_tracker")

await pt.get_poses(body_names: List[str], *, extra=None, timeout=None) -> Dict[str, PoseInFrame]
```

### Audio In

**Import:** `from viam.components.audio_in import AudioIn`
**API:** `rdk:component:audio_in`

```python
audio_in = AudioIn.from_robot(robot, "my_audio_in")

await audio_in.get_audio(codec: str, duration_seconds: float, previous_timestamp_ns: int, *, timeout=None) -> AudioIn.AudioStream
await audio_in.get_properties(*, timeout=None) -> AudioIn.Properties
```

### Audio Out

**Import:** `from viam.components.audio_out import AudioOut`
**API:** `rdk:component:audio_out`

```python
audio_out = AudioOut.from_robot(robot, "my_audio_out")

await audio_out.play(data: bytes, info: Optional[AudioInfo] = None, *, extra=None, timeout=None) -> None
await audio_out.get_properties(*, extra=None, timeout=None) -> AudioOut.Properties
```

---

## Service Interfaces

All services inherit from `ServiceBase` and share `do_command()`, `get_status()`,
and `close()` from `ResourceBase`.

### Vision

**Import:** `from viam.services.vision import Vision, CaptureAllResult`
**Types:** `from viam.proto.service.vision import Detection, Classification`
**API:** `rdk:service:vision`

```python
vision = Vision.from_robot(robot, "my_vision")

await vision.capture_all_from_camera(
    camera_name: str,
    return_image: bool = False,
    return_classifications: bool = False,
    return_detections: bool = False,
    return_object_point_clouds: bool = False,
    *, extra=None, timeout=None
) -> CaptureAllResult
    # CaptureAllResult.image: Optional[ViamImage]
    # CaptureAllResult.classifications: Optional[List[Classification]]
    # CaptureAllResult.detections: Optional[List[Detection]]
    # CaptureAllResult.objects: Optional[List[PointCloudObject]]
    # CaptureAllResult.extra: Optional[Mapping[str, ValueTypes]]

await vision.get_detections_from_camera(camera_name: str, *, extra=None, timeout=None)
    -> List[Detection]
await vision.get_detections(image: ViamImage, *, extra=None, timeout=None)
    -> List[Detection]
await vision.get_classifications_from_camera(camera_name: str, count: int, *, extra=None, timeout=None)
    -> List[Classification]
await vision.get_classifications(image: ViamImage, count: int, *, extra=None, timeout=None)
    -> List[Classification]
await vision.get_object_point_clouds(camera_name: str, *, extra=None, timeout=None)
    -> List[PointCloudObject]
await vision.get_properties(*, extra=None, timeout=None) -> Vision.Properties
    # Properties: classifications_supported, detections_supported, object_point_clouds_supported
```

**Detection fields:** `x_min`, `y_min`, `x_max`, `y_max`, `confidence`, `class_name`

**Classification fields:** `class_name`, `confidence`

### Motion

**Import:** `from viam.services.motion import Motion`
**Types:** `from viam.proto.common import Pose, PoseInFrame, WorldState, GeoPoint, GeoGeometry, Geometry, Transform`
**Types:** `from viam.proto.service.motion import Constraints, MotionConfiguration, PlanStatusWithID`
**API:** `rdk:service:motion`

```python
motion = Motion.from_robot(robot, "builtin")

await motion.move(
    component_name: str,
    destination: PoseInFrame,
    world_state: Optional[WorldState] = None,
    constraints: Optional[Constraints] = None,
    *, extra=None, timeout=None
) -> bool

await motion.move_on_globe(
    component_name: str,
    destination: GeoPoint,
    movement_sensor_name: str,
    obstacles: Optional[Sequence[GeoGeometry]] = None,
    heading: Optional[float] = None,
    configuration: Optional[MotionConfiguration] = None,
    *, bounding_regions=None, extra=None, timeout=None
) -> str  # returns execution_id

await motion.move_on_map(
    component_name: str,
    destination: Pose,
    slam_service_name: str,
    configuration: Optional[MotionConfiguration] = None,
    obstacles: Optional[Sequence[Geometry]] = None,
    *, extra=None, timeout=None
) -> str  # returns execution_id

await motion.stop_plan(component_name: str, *, extra=None, timeout=None)
await motion.get_plan(
    component_name: str,
    last_plan_only: bool = False,
    execution_id: Optional[str] = None,
    *, extra=None, timeout=None
) -> Motion.Plan  # GetPlanResponse

await motion.list_plan_statuses(only_active_plans: bool = False, *, extra=None, timeout=None)
    -> Sequence[PlanStatusWithID]

await motion.get_pose(
    component_name: str,
    destination_frame: str,
    supplemental_transforms: Optional[Sequence[Transform]] = None,
    *, extra=None, timeout=None
) -> PoseInFrame
```

### SLAM

**Import:** `from viam.services.slam import SLAM`
**API:** `rdk:service:slam`

```python
slam = SLAM.from_robot(robot, "my_slam")

await slam.get_position(*, timeout) -> Pose
await slam.get_point_cloud_map(return_edited_map: bool = False, *, timeout) -> List[bytes]
await slam.get_internal_state(*, timeout) -> List[bytes]
await slam.get_properties(*, timeout) -> SLAM.Properties
    # Properties = GetPropertiesResponse
```

### Navigation

**Import:** `from viam.services.navigation import Navigation`
**Types:** `from viam.services.navigation import GeoPoint, GeoGeometry, Waypoint, Path, Mode, MapType`
**API:** `rdk:service:navigation`

```python
nav = Navigation.from_robot(robot, "my_nav")

await nav.get_location(*, timeout) -> GeoPoint
await nav.get_waypoints(*, timeout) -> List[Waypoint]
await nav.add_waypoint(point: GeoPoint, *, timeout)
await nav.remove_waypoint(id: str, *, timeout)
await nav.get_obstacles(*, timeout) -> List[GeoGeometry]
await nav.get_paths(*, timeout) -> List[Path]
await nav.get_mode(*, timeout) -> Mode.ValueType
await nav.set_mode(mode: Mode.ValueType, *, timeout)
await nav.get_properties(*, timeout) -> MapType.ValueType
```

**Mode values:** `Mode.MODE_MANUAL`, `Mode.MODE_WAYPOINT`

### MLModel

**Import:** `from viam.services.mlmodel import MLModel`
**Types:** `from viam.proto.service.mlmodel import Metadata`
**API:** `rdk:service:mlmodel`

```python
mlmodel = MLModel.from_robot(robot, "my_mlmodel")

await mlmodel.infer(input_tensors: Dict[str, NDArray], *, extra=None, timeout=None)
    -> Dict[str, NDArray]
await mlmodel.metadata(*, extra=None, timeout=None) -> Metadata
```

**Important:** Input and output tensors are `numpy.NDArray` objects. This is one
of the few places the SDK has a hard dependency on NumPy.

### Discovery

**Import:** `from viam.services.discovery import Discovery`
**API:** `rdk:service:discovery`

```python
discovery = Discovery.from_robot(robot, "my_discovery")

await discovery.discover_resources(*, extra=None, timeout=None) -> List[ComponentConfig]
```

### WorldStateStore

**Import:** `from viam.services.worldstatestore import WorldStateStore`
**API:** `rdk:service:world_state_store`

```python
wss = WorldStateStore.from_robot(robot, "builtin")

await wss.list_uuids(*, extra=None, timeout=None) -> List[bytes]
await wss.get_transform(uuid: bytes, *, extra=None, timeout=None) -> Transform
# Additional methods: set_transform, delete_transform, stream_transform_changes
```

### Generic Service

**Import:** `from viam.services.generic import Generic`
**API:** `rdk:service:generic`

Only has `do_command()` from `ServiceBase`. No additional methods.

---

## Module Development

### Two Approaches

1. **EasyResource mixin** (recommended for most cases) — minimal boilerplate
2. **Manual registration** — full control over lifecycle

### EasyResource Approach (Recommended)

```python
import asyncio
from viam.components.sensor import Sensor
from viam.resource.easy_resource import EasyResource
from viam.module.module import Module


class MySensor(Sensor, EasyResource):
    MODEL = "my-org:my-family:my-sensor"

    async def get_readings(self, **kwargs):
        return {"temperature": 22.5}


if __name__ == '__main__':
    asyncio.run(Module.run_from_registry())
```

`EasyResource` handles:
- Parsing `MODEL` string into `Model(ModelFamily(ns, family), name)`
- Auto-registering with the global `Registry` via `__init_subclass__`
- Providing a default `new()` factory and `validate_config()`
- `Module.run_from_registry()` picks up all registered models automatically

### Manual Registration Approach

```python
import asyncio
from typing import ClassVar, Mapping, Optional, Sequence, Tuple

from typing_extensions import Self

from viam.components.sensor import Sensor
from viam.module.module import Module
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.registry import Registry, ResourceCreatorRegistration
from viam.resource.types import Model, ModelFamily
from viam.utils import SensorReading


class MySensor(Sensor):
    MODEL: ClassVar[Model] = Model(ModelFamily("my-org", "my-family"), "my-sensor")

    def __init__(self, name: str):
        super().__init__(name)

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        sensor = cls(config.name)
        sensor.reconfigure(config, dependencies)
        return sensor

    @classmethod
    def validate_config(cls, config: ComponentConfig) -> Tuple[Sequence[str], Sequence[str]]:
        # Return (required_dependencies, optional_dependencies)
        return [], []

    def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        # Read attributes from config
        if "multiplier" in config.attributes.fields:
            self.multiplier = config.attributes.fields["multiplier"].number_value
        else:
            self.multiplier = 1.0

    async def get_readings(self, *, extra=None, **kwargs) -> Mapping[str, SensorReading]:
        return {"signal": 1 * self.multiplier}

    async def close(self):
        pass  # cleanup


async def main():
    Registry.register_resource_creator(
        Sensor.API,
        MySensor.MODEL,
        ResourceCreatorRegistration(MySensor.new, MySensor.validate_config)
    )
    module = Module.from_args()
    module.add_model_from_registry(Sensor.API, MySensor.MODEL)
    await module.start()


if __name__ == "__main__":
    asyncio.run(main())
```

### Module Class

```python
from viam.module.module import Module

# Class methods for entry points:
Module.from_args() -> Module          # parse socket_path, --log-level from CLI args
Module.run_from_registry()            # auto-discover all registered models, start serving
Module.run_with_models(*models)       # explicit list of model classes

# Instance methods:
module.add_model_from_registry(api: API, model: Model)
await module.start()
await module.stop()
module.set_ready(ready: bool)         # signal readiness to viam-server
```

### Reconfigurable and Stoppable Protocols

```python
from viam.module.types import Reconfigurable, Stoppable

class MyComponent(Sensor, Reconfigurable, Stoppable):
    def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        # Called when config changes at runtime
        ...

    def stop(self, *, extra=None, timeout=None, **kwargs):
        # Called when resource is removed or reconfigured
        ...
```

If a resource implements `Reconfigurable`, the module calls `reconfigure()` on
config changes. Otherwise, the old resource is stopped and a new one is created.

If a resource implements `Stoppable`, `stop()` is called before removal.

### stub_model Decorator

For incremental development — stubs out abstract methods so the class can be
instantiated without implementing everything:

```python
from viam.resource.easy_resource import stub_model

@stub_model
class MyMotor(Motor, EasyResource):
    MODEL = "my-org:motor:prototype"
    # No abstract methods implemented yet - they'll raise MethodNotImplementedError at runtime
```

### validate_config Return Signature

```python
@classmethod
def validate_config(cls, config: ComponentConfig) -> Tuple[Sequence[str], Sequence[str]]:
    """
    Returns:
        Tuple of (required_dependencies, optional_dependencies)
        Each is a sequence of resource name strings, e.g. ["rdk:component:sensor/my_sensor"]
    """
    return ["rdk:component:camera/my_camera"], []
```

### Accessing Config Attributes

Config attributes come as a protobuf `Struct`:

```python
def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
    attrs = config.attributes.fields
    if "threshold" in attrs:
        self.threshold = attrs["threshold"].number_value
    if "name" in attrs:
        self.label = attrs["name"].string_value
    if "enabled" in attrs:
        self.enabled = attrs["enabled"].bool_value
```

### Accessing Dependencies

```python
def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
    # dependencies is keyed by ResourceName
    for rn, resource in dependencies.items():
        if rn.subtype == "camera":
            self.camera = resource  # This is a Camera client
```

---

## Type System

### Common Protobuf Types

All from `viam.proto.common`:

```python
from viam.proto.common import (
    Pose,           # x, y, z (mm), o_x, o_y, o_z, theta (degrees)
    PoseInFrame,    # reference_frame: str, pose: Pose
    Vector3,        # x, y, z
    GeoPoint,       # latitude, longitude
    GeoGeometry,    # location: GeoPoint, geometries: list
    Geometry,       # center: Pose, various shape fields
    Orientation,    # o_x, o_y, o_z, theta
    WorldState,     # obstacles, transforms
    Transform,      # reference_frame, pose_in_observer_frame, physical_object
    ResourceName,   # namespace, type, subtype, name
)
```

### Constructing Types

```python
# Pose (position in mm, orientation as vector + theta in degrees)
pose = Pose(x=100, y=200, z=300, o_x=0, o_y=0, o_z=1, theta=90)

# PoseInFrame
pif = PoseInFrame(reference_frame="world", pose=pose)

# Vector3
v = Vector3(x=1.0, y=2.0, z=3.0)

# GeoPoint
gp = GeoPoint(latitude=40.7128, longitude=-74.0060)

# WorldState
ws = WorldState(
    obstacles=[GeometriesInFrame(...)],
    transforms=[Transform(...)]
)

# JointPositions (for arms)
from viam.proto.component.arm import JointPositions
jp = JointPositions(values=[0.0, 45.0, 90.0, 0.0, 0.0, 0.0])
```

### Go vs. Python Type Differences

| Go Type | Python Type | Notes |
|---|---|---|
| `spatialmath.Pose` | `viam.proto.common.Pose` | Python uses protobuf directly |
| `referenceframe.PoseInFrame` | `viam.proto.common.PoseInFrame` | Same |
| `r3.Vector` | `viam.proto.common.Vector3` | Same |
| `geo.Point` | `viam.proto.common.GeoPoint` | Same |
| `spatialmath.Orientation` | `viam.proto.common.Orientation` | Same |
| `referenceframe.WorldState` | `viam.proto.common.WorldState` | Same |
| `resource.Name` | `viam.proto.common.ResourceName` | Same |
| `[]referenceframe.Input` (radians) | `JointPositions.values` (degrees) | **Units differ** |
| Error via `error` return | Exception raised | Python uses exceptions |
| `context.Context` | `timeout` kwarg | No context objects in Python |
| CamelCase methods | snake_case methods | e.g., `GetEndPosition` -> `get_end_position` |
| Synchronous | `async`/`await` everywhere | All resource methods are async |

---

## Async Patterns

### Basic Connection + Usage

```python
import asyncio
from viam.robot.client import RobotClient
from viam.rpc.dial import DialOptions, Credentials
from viam.components.sensor import Sensor


async def main():
    opts = RobotClient.Options.with_api_key(
        api_key='<KEY>',
        api_key_id='<KEY-ID>'
    )
    robot = await RobotClient.at_address('<ADDRESS>', opts)

    try:
        sensor = Sensor.from_robot(robot, "my_sensor")
        readings = await sensor.get_readings()
        print(readings)
    finally:
        await robot.close()


if __name__ == "__main__":
    asyncio.run(main())
```

### Context Manager Pattern

```python
async def main():
    opts = RobotClient.Options.with_api_key(api_key='...', api_key_id='...')
    robot = await RobotClient.at_address('...', opts)

    async with robot:
        sensor = Sensor.from_robot(robot, "my_sensor")
        readings = await sensor.get_readings()
```

**Warning:** `RobotClient.at_address()` returns the robot directly (not a context
manager factory). You call `await` once to get the robot, then use `async with`
on the result:

```python
# CORRECT:
robot = await RobotClient.at_address(addr, opts)
async with robot:
    ...

# ALSO CORRECT:
robot = await RobotClient.at_address(addr, opts)
try:
    ...
finally:
    await robot.close()
```

### Concurrent Operations

```python
import asyncio

async def main():
    robot = await RobotClient.at_address(addr, opts)
    sensor1 = Sensor.from_robot(robot, "sensor1")
    sensor2 = Sensor.from_robot(robot, "sensor2")

    # Concurrent reads
    r1, r2 = await asyncio.gather(
        sensor1.get_readings(),
        sensor2.get_readings()
    )
```

### Error Handling

```python
from grpclib import GRPCError

try:
    pos = await arm.get_end_position()
except GRPCError as e:
    print(f"gRPC error: {e.status} - {e.message}")
except ConnectionError:
    print("Lost connection to robot")
```

### Timeout Pattern

Most methods accept a `timeout` keyword argument (seconds):

```python
# 5-second timeout
pos = await arm.get_end_position(timeout=5.0)
```

---

## Ecosystem Integration

### OpenCV / NumPy with Camera Images

The SDK returns `ViamImage` objects. To convert to OpenCV/NumPy:

```python
import numpy as np
from PIL import Image
import io

from viam.components.camera import Camera
from viam.media.video import CameraMimeType

camera = Camera.from_robot(robot, "my_camera")

# Get images — returns list of NamedImage
images, metadata = await camera.get_images()
img = images[0]

# ViamImage -> PIL Image -> numpy array
pil_image = Image.open(io.BytesIO(img.data))
np_array = np.array(pil_image)

# For JPEG or PNG data specifically:
# The img.data is raw JPEG/PNG bytes, so PIL can decode directly.
# For VIAM_RGBA format, you need to strip the 12-byte header first:
if img.mime_type == CameraMimeType.VIAM_RGBA:
    rgba_data = img.data[12:]  # skip 12-byte header (magic + width + height)
    np_array = np.frombuffer(rgba_data, dtype=np.uint8).reshape(img.height, img.width, 4)

# numpy -> OpenCV (BGR)
import cv2
bgr = cv2.cvtColor(np_array, cv2.COLOR_RGB2BGR)
```

### Creating ViamImage from NumPy/OpenCV

```python
from viam.media.video import ViamImage, CameraMimeType
import cv2

# OpenCV BGR -> JPEG bytes -> ViamImage
success, jpeg_bytes = cv2.imencode('.jpg', bgr_image)
viam_img = ViamImage(jpeg_bytes.tobytes(), CameraMimeType.JPEG)

# PIL -> JPEG bytes -> ViamImage
import io
from PIL import Image
buf = io.BytesIO()
pil_image.save(buf, format='JPEG')
viam_img = ViamImage(buf.getvalue(), CameraMimeType.JPEG)
```

### Point Cloud Data with Open3D

```python
import numpy as np
import open3d as o3d

camera = Camera.from_robot(robot, "my_camera")
data, mime = await camera.get_point_cloud()

# Write PCD data to temp file, then load with Open3D
with open("/tmp/pointcloud.pcd", "wb") as f:
    f.write(data)
pcd = o3d.io.read_point_cloud("/tmp/pointcloud.pcd")
points = np.asarray(pcd.points)
```

### MLModel with NumPy/PyTorch

```python
import numpy as np
from viam.services.mlmodel import MLModel

mlmodel = MLModel.from_robot(robot, "my_model")

# NumPy input
image_data = np.zeros((1, 384, 384, 3), dtype=np.uint8)
output = await mlmodel.infer({"image": image_data})

# PyTorch conversion
import torch
tensor = torch.from_numpy(output["detections"])
```

### Depth Image to Array

```python
camera = Camera.from_robot(robot, "my_depth_camera")
images, _ = await camera.get_images()

for img in images:
    if img.mime_type == CameraMimeType.VIAM_RAW_DEPTH:
        depth_array = img.bytes_to_depth_array()  # List[List[int]]
        depth_np = np.array(depth_array, dtype=np.uint16)
```

---

## CameraMimeType Constants

```python
from viam.media.video import CameraMimeType

CameraMimeType.JPEG          # "image/jpeg"
CameraMimeType.PNG           # "image/png"
CameraMimeType.VIAM_RGBA     # "image/vnd.viam.rgba"
CameraMimeType.VIAM_RAW_DEPTH  # "image/vnd.viam.dep"
CameraMimeType.PCD           # "pointcloud/pcd"
CameraMimeType.CUSTOM("image/webp")  # custom mime type
```

---

## Logging

```python
from viam import logging

# In a module, use the resource logger
class MyComponent(Sensor, EasyResource):
    async def get_readings(self, **kwargs):
        self.logger.info("Taking reading")
        self.logger.debug("Debug info")
        return {"val": 42}

# In client code, use viam.logging
logger = logging.getLogger(__name__)
```

Module logs are forwarded to `viam-server` via gRPC when the module is running
as a child process. The `--log-level` CLI argument controls the log level.

---

## API and Model Strings

### Format

- **API:** `namespace:type:subtype` (e.g., `rdk:component:sensor`)
- **Model:** `namespace:family:name` (e.g., `my-org:my-family:my-sensor`)
- **ResourceName string:** `namespace:type:subtype/name` (e.g., `rdk:component:sensor/my_sensor`)

### Built-in API Constants

Every component and service class has an `API` class variable:

```python
Arm.API        # API("rdk", "component", "arm")
Sensor.API     # API("rdk", "component", "sensor")
Vision.API     # API("rdk", "service", "vision")
Motion.API     # API("rdk", "service", "motion")
# etc.
```

### Creating Custom APIs and Models

```python
from viam.resource.types import API, Model, ModelFamily

# Custom API (for a new resource type)
my_api = API("my-org", "component", "my-custom-type")

# Custom Model
my_model = Model(ModelFamily("my-org", "my-family"), "my-model-name")

# Or from string
my_model = Model.from_string("my-org:my-family:my-model-name")
```
