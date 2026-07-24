# Viam Go SDK -- Platform Components & Services Cheatsheet

Quick reference companion to `SKILL.md`. Load when you need interface signatures,
import paths, unit tables, or common patterns at a glance. Built from
`viamrobotics/rdk` source, April 2026.

---

## Component Interface Summary

| Component | Package | API String | Key Methods (beyond Resource) | Embeds |
|-----------|---------|------------|-------------------------------|--------|
| Base | `components/base` | `rdk:component:base` | MoveStraight, Spin, SetPower, SetVelocity, Properties | Actuator, Shaped |
| Board | `components/board` | `rdk:component:board` | AnalogByName, DigitalInterruptByName, GPIOPinByName, SetPowerMode, StreamTicks | -- |
| Motor | `components/motor` | `rdk:component:motor` | SetPower, GoFor, GoTo, SetRPM, ResetZeroPosition, Position, Properties, IsPowered | Actuator |
| Servo | `components/servo` | `rdk:component:servo` | Move, Position | Actuator |
| Sensor | `components/sensor` | `rdk:component:sensor` | Readings (via resource.Sensor) | Sensor |
| MovementSensor | `components/movementsensor` | `rdk:component:movement_sensor` | Position, LinearVelocity, AngularVelocity, LinearAcceleration, CompassHeading, Orientation, Properties, Accuracy | Sensor |
| Encoder | `components/encoder` | `rdk:component:encoder` | Position, ResetPosition, Properties | -- |
| Gripper | `components/gripper` | `rdk:component:gripper` | Open, Grab, IsHoldingSomething | Actuator, Shaped, InputEnabled |
| Gantry | `components/gantry` | `rdk:component:gantry` | Position, MoveToPosition, Lengths, Home | Actuator, Shaped, InputEnabled |
| InputController | `components/input` | `rdk:component:input_controller` | Controls, Events, RegisterControlCallback | -- |
| PowerSensor | `components/powersensor` | `rdk:component:power_sensor` | Voltage, Current, Power, Readings | Sensor |
| AudioIn | `components/audioin` | `rdk:component:audio_in` | GetAudio, Properties | -- |
| AudioOut | `components/audioout` | `rdk:component:audio_out` | Play, Properties | -- |
| Button | `components/button` | `rdk:component:button` | Push | -- |
| Switch | `components/switch` | `rdk:component:switch` | SetPosition, GetPosition, GetNumberOfPositions | -- |
| PoseTracker | `components/posetracker` | `rdk:component:pose_tracker` | Poses | -- |
| Generic | `components/generic` | `rdk:component:generic` | (DoCommand only) | -- |

---

## Service Interface Summary

| Service | Package | API String | Key Methods |
|---------|---------|------------|-------------|
| Navigation | `services/navigation` | `rdk:service:navigation` | Mode, SetMode, Location, Waypoints, AddWaypoint, RemoveWaypoint, Obstacles, Paths, Properties |
| SLAM | `services/slam` | `rdk:service:slam` | Position, PointCloudMap, InternalState, Properties |
| Data Manager | `services/datamanager` | `rdk:service:data_manager` | Sync, UploadBinaryDataToDatasets, UploadImageToDatasets |
| Discovery | `services/discovery` | `rdk:service:discovery` | DiscoverResources |
| WorldStateStore | `services/worldstatestore` | `rdk:service:world_state_store` | ListUUIDs, GetTransform, StreamTransformChanges |
| BaseRemoteControl | `services/baseremotecontrol` | `rdk:service:base_remote_control` | Close, ControllerInputs |
| Generic | `services/generic` | `rdk:service:generic` | (DoCommand only) |

---

## Resource Lifecycle Method Signatures

```go
// Every resource implements:
Name() resource.Name
Reconfigure(ctx context.Context, deps resource.Dependencies, conf resource.Config) error
DoCommand(ctx context.Context, cmd map[string]interface{}) (map[string]interface{}, error)
Status(ctx context.Context) (map[string]interface{}, error)
Close(ctx context.Context) error

// Actuator (base, motor, servo, gripper, gantry):
IsMoving(context.Context) (bool, error)
Stop(context.Context, map[string]interface{}) error

// Sensor (sensor, movement_sensor, power_sensor):
Readings(ctx context.Context, extra map[string]interface{}) (map[string]interface{}, error)

// Shaped (base, gripper, gantry):
Geometries(context.Context, map[string]interface{}) ([]spatialmath.Geometry, error)
```

---

## Import Paths

All under `go.viam.com/rdk/`:

| Resource | Import |
|----------|--------|
| Base | `go.viam.com/rdk/components/base` |
| Board | `go.viam.com/rdk/components/board` |
| Motor | `go.viam.com/rdk/components/motor` |
| Servo | `go.viam.com/rdk/components/servo` |
| Sensor | `go.viam.com/rdk/components/sensor` |
| Movement Sensor | `go.viam.com/rdk/components/movementsensor` |
| Encoder | `go.viam.com/rdk/components/encoder` |
| Gripper | `go.viam.com/rdk/components/gripper` |
| Gantry | `go.viam.com/rdk/components/gantry` |
| Input Controller | `go.viam.com/rdk/components/input` |
| Power Sensor | `go.viam.com/rdk/components/powersensor` |
| Audio In | `go.viam.com/rdk/components/audioin` |
| Audio Out | `go.viam.com/rdk/components/audioout` |
| Button | `go.viam.com/rdk/components/button` |
| Switch | `go.viam.com/rdk/components/switch` (package: `toggleswitch`) |
| Pose Tracker | `go.viam.com/rdk/components/posetracker` |
| Generic (component) | `go.viam.com/rdk/components/generic` |
| Navigation | `go.viam.com/rdk/services/navigation` |
| SLAM | `go.viam.com/rdk/services/slam` |
| Data Manager | `go.viam.com/rdk/services/datamanager` |
| Discovery | `go.viam.com/rdk/services/discovery` |
| World State Store | `go.viam.com/rdk/services/worldstatestore` |
| Base Remote Control | `go.viam.com/rdk/services/baseremotecontrol` |
| Generic (service) | `go.viam.com/rdk/services/generic` |
| Resource API | `go.viam.com/rdk/resource` |
| Logging | `go.viam.com/rdk/logging` |
| Module entry point | `go.viam.com/rdk/module` |
| Spatial math | `go.viam.com/rdk/spatialmath` |
| Reference frame | `go.viam.com/rdk/referenceframe` |
| Point cloud | `go.viam.com/rdk/pointcloud` |

---

## Unit Conventions Per Component

| Component | Measurement | Unit |
|-----------|------------|------|
| Base | Distance | mm |
| Base | Linear speed | mm/s |
| Base | Angle | degrees |
| Base | Angular speed | deg/s |
| Base | Power | fraction [-1, 1] |
| Base | Properties | meters |
| Motor | Power | fraction [-1, 1] |
| Motor | Speed | RPM |
| Motor | Position | revolutions |
| Servo | Angle | degrees [0, 180] |
| Encoder | Position (ticks) | ticks (relative) |
| Encoder | Position (degrees) | degrees (absolute) |
| Gantry | Position | mm |
| Gantry | Speed | mm/s |
| Gantry | Lengths | mm |
| MovementSensor | Position | lat/long degrees, altitude meters |
| MovementSensor | Linear velocity | m/s |
| MovementSensor | Angular velocity | deg/s |
| MovementSensor | Linear acceleration | m/s^2 |
| MovementSensor | Compass heading | degrees [0, 360) |
| PowerSensor | Voltage | volts |
| PowerSensor | Current | amperes |
| PowerSensor | Power | watts |
| Board analog | Value | bits (ADC reading) |
| Board PWM | Duty cycle | fraction [0, 1] |
| Board PWM | Frequency | Hz |
| Navigation | Location | lat/long degrees |

---

## Config Field Tables

### Base Config (generic)
```json
{
  "width_mm": 300,
  "wheel_circumference_mm": 200,
  "spin_slip_factor": 1.0,
  "left": ["motor_left"],
  "right": ["motor_right"]
}
```

### Motor Config (GPIO)
```json
{
  "board": "my_board",
  "pins": {"a": "13", "b": "15", "pwm": "18"},
  "encoder": "my_encoder",
  "ticks_per_rotation": 200,
  "max_rpm": 100
}
```

### Encoder Config (incremental)
```json
{
  "board": "my_board",
  "pins": {"i": "11", "a": "13", "b": "15"}
}
```

### Servo Config
```json
{
  "board": "my_board",
  "pin": "16"
}
```

### Movement Sensor Config (GPS)
```json
{
  "connection_type": "serial",
  "serial_path": "/dev/ttyUSB0",
  "serial_baud_rate": 9600
}
```

### Navigation Service Config
```json
{
  "base": "my_base",
  "movement_sensor": "my_gps",
  "obstacles": [],
  "store": {"type": "memory"}
}
```

### Data Manager Config
```json
{
  "sync_interval_mins": 5,
  "capture_dir": "/tmp/viam-data"
}
```

---

## Resource API Quick Reference

### API Triplet: `namespace:type:subtype`
```go
api := resource.APINamespaceRDK.WithComponentType("motor")  // rdk:component:motor
api := resource.APINamespaceRDK.WithServiceType("slam")     // rdk:service:slam
api := resource.NewAPI("acme", "component", "gizmo")        // acme:component:gizmo
```

### Model Triplet: `namespace:family:name`
```go
model := resource.NewModel("acme", "demo", "my-motor")          // acme:demo:my-motor
model := resource.DefaultModelFamily.WithModel("gpio")           // rdk:builtin:gpio
model, _ := resource.NewModelFromString("acme:demo:my-motor")   // from string
```

### Name
```go
name := motor.Named("my_motor")                              // rdk:component:motor/my_motor
name := resource.NewName(api, "my_motor")                    // generic
name, _ := resource.NewFromString("rdk:component:motor/m1")  // from string
```

### Registration Pattern
```go
resource.RegisterComponent(motor.API, myModel, resource.Registration[motor.Motor, *Config]{
    Constructor: newMyMotor,
})
```

### Config Validation Pattern
```go
func (c *Config) Validate(path string) ([]string, []string, error) {
    if c.RequiredField == "" {
        return nil, nil, resource.NewConfigValidationFieldRequiredError(path, "required_field")
    }
    return []string{c.RequiredDep}, []string{c.OptionalDep}, nil
}
```

---

## Common Error Patterns and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `dependency X is not ready yet` | Dependency failed to construct | Check the dependency resource's own errors; fix its config |
| `incorrect config type: NativeConfig` | Config struct mismatch | Ensure type passed to `NativeConfig[T]` matches type in `Registration` |
| `cannot register a nil constructor` | Missing Constructor field | Provide Constructor in Registration |
| `reserved character : used in name` | Colons in resource name | Resource names cannot contain `:` or `+` |
| `not a valid API config string` | Malformed API triplet | Use `namespace:type:subtype` format |
| `not a valid model name` | Malformed model triplet | Use `namespace:family:name` format |
| Motor `NewZeroRPMError` | RPM near zero | Check RPM value; must be >= 0.1 |
| Board PWM `cannot set duty cycle` | Duty cycle > 1.0 or < 0.0 | Use range [0.0, 1.0] |
| Encoder `PositionTypeUnspecified` | Didn't specify position type | Pass `encoder.PositionTypeTicks` or `encoder.PositionTypeDegrees` |
| `FromRobot is deprecated` | Using old helper | Switch to `FromProvider(machine, "name")` |
| Movement sensor returns NaN | Method not implemented | Check `Properties()` to see which methods are supported |
| Navigation `map type unspecified` | Bad map type string | Use `"GPS"` or `"None"` |
| SLAM streaming empty | Didn't concatenate chunks | Use `slam.PointCloudMapFull()` or `slam.InternalStateFull()` helpers |

---

## Pattern: Getting Any Resource

```go
// Preferred (works with Robot or Dependencies)
myMotor, err := motor.FromProvider(provider, "my_motor")

// From Dependencies in a constructor
myBoard, err := board.FromDependencies(deps, "my_board")  // deprecated but works

// Generic typed lookup
res, err := resource.FromProvider[motor.Motor](provider, motor.Named("my_motor"))

// Type assertion
typedRes, err := resource.AsType[motor.Motor](genericResource)
```

---

## Pattern: Module main()

```go
func main() {
    module.ModularMain(
        resource.APIModel{API: motor.API, Model: myModel},
        resource.APIModel{API: sensor.API, Model: mySensorModel},
        // list all models this module provides
    )
}
```

---

## Pattern: Data Capture on Any Component

In robot config JSON, add `service_configs` to the component:

```json
{
  "name": "my_sensor",
  "api": "rdk:component:sensor",
  "model": "rdk:builtin:my_model",
  "service_configs": [{
    "type": "rdk:service:data_manager",
    "attributes": {
      "capture_methods": [{
        "method": "Readings",
        "capture_frequency_hz": 1.0
      }]
    }
  }]
}
```

Common capture methods per component:
- Sensor: `"Readings"`
- Motor: `"Position"`, `"IsPowered"`
- Servo: `"Position"`
- MovementSensor: `"Position"`, `"LinearVelocity"`, `"AngularVelocity"`, `"CompassHeading"`, `"LinearAcceleration"`, `"Orientation"`, `"Readings"`
- Encoder: `"TicksCount"`
- PowerSensor: `"Voltage"`, `"Current"`, `"Power"`, `"Readings"`
- Board: `"Analogs"`, `"GPIOs"`
- SLAM: `"Position"`, `"PointCloudMap"`
