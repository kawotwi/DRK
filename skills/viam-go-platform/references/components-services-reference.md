# Viam Go SDK -- Components & Services Reference (Non-Manipulation)

Deep reference for all Viam RDK components and services NOT covered by the
`viam-go-motion-vision` skill (arm, camera, vision, motion). Built from
`viamrobotics/rdk` source, April 2026.

---

## Table of Contents

1. [Base](#base)
2. [Board](#board)
3. [Motor](#motor)
4. [Servo](#servo)
5. [Sensor](#sensor)
6. [Movement Sensor](#movement-sensor)
7. [Encoder](#encoder)
8. [Gripper](#gripper)
9. [Gantry](#gantry)
10. [Input Controller](#input-controller)
11. [Power Sensor](#power-sensor)
12. [Audio Input](#audio-input)
13. [Audio Output](#audio-output)
14. [Button](#button)
15. [Switch](#switch)
16. [Pose Tracker](#pose-tracker)
17. [Generic Component](#generic-component)
18. [Navigation Service](#navigation-service)
19. [SLAM Service](#slam-service)
20. [Data Manager Service](#data-manager-service)
21. [Discovery Service](#discovery-service)
22. [World State Store Service](#world-state-store-service)
23. [Base Remote Control Service](#base-remote-control-service)
24. [Generic Service](#generic-service)
25. [Common Integration Patterns](#common-integration-patterns)

---

## Base

**Package:** `go.viam.com/rdk/components/base`
**API string:** `rdk:component:base`
**Protobuf:** `go.viam.com/api/component/base/v1`

### Interface

```go
type Base interface {
    resource.Resource   // Name, Reconfigure, DoCommand, Close
    resource.Actuator   // IsMoving, Stop
    resource.Shaped     // Geometries

    // MoveStraight moves the robot straight a given distance at a given speed.
    // Blocks until completed or cancelled. Distance=0 or speed=0 stops the base.
    MoveStraight(ctx context.Context, distanceMm int, mmPerSec float64,
        extra map[string]interface{}) error

    // Spin spins the robot by angleDeg at degsPerSec.
    // Positive speed + positive angle = turn left (built-in drivers).
    // Blocks until completed or cancelled.
    Spin(ctx context.Context, angleDeg, degsPerSec float64,
        extra map[string]interface{}) error

    // SetPower sets linear and angular power vectors.
    // Linear: positive Y = forward. Angular: positive Z = turn left.
    // Values in [-1.0, 1.0].
    SetPower(ctx context.Context, linear, angular r3.Vector,
        extra map[string]interface{}) error

    // SetVelocity sets linear velocity (mm/s) and angular velocity (deg/s).
    // Linear: positive Y = forward. Angular: positive Z = turn left.
    SetVelocity(ctx context.Context, linear, angular r3.Vector,
        extra map[string]interface{}) error

    // Properties returns physical dimensions of the base.
    Properties(ctx context.Context, extra map[string]interface{}) (Properties, error)
}
```

### Properties Struct

```go
type Properties struct {
    TurningRadiusMeters      float64
    WidthMeters              float64
    WheelCircumferenceMeters float64
}
```

### Helper Functions

```go
base.Named(name string) resource.Name
base.FromProvider(provider resource.Provider, name string) (Base, error)
base.NamesFromRobot(r robot.Robot) []string
```

### Unit Conventions

| Quantity | Unit |
|----------|------|
| Distance | mm |
| Linear speed/velocity | mm/s |
| Angle | degrees |
| Angular speed | degrees/s |
| Power | fraction [-1.0, 1.0] |
| Properties dimensions | meters |

---

## Board

**Package:** `go.viam.com/rdk/components/board`
**API string:** `rdk:component:board`
**Protobuf:** `go.viam.com/api/component/board/v1`

### Board Interface

```go
type Board interface {
    resource.Resource

    // AnalogByName returns an analog pin by name.
    AnalogByName(name string) (Analog, error)

    // DigitalInterruptByName returns a digital interrupt by name.
    DigitalInterruptByName(name string) (DigitalInterrupt, error)

    // GPIOPinByName returns a GPIOPin by name.
    GPIOPinByName(name string) (GPIOPin, error)

    // SetPowerMode sets the board to the given power mode.
    // Duration is optional; if provided, board exits mode after that time.
    SetPowerMode(ctx context.Context, mode pb.PowerMode, duration *time.Duration,
        extra map[string]interface{}) error

    // StreamTicks starts a stream of digital interrupt ticks.
    StreamTicks(ctx context.Context, interrupts []DigitalInterrupt,
        ch chan Tick, extra map[string]interface{}) error
}
```

### GPIOPin Sub-Interface

```go
type GPIOPin interface {
    // Set sets the pin to either low or high.
    Set(ctx context.Context, high bool, extra map[string]interface{}) error

    // Get gets the high/low state of the pin.
    Get(ctx context.Context, extra map[string]interface{}) (bool, error)

    // PWM gets the pin's given duty cycle (0.0 to 1.0).
    PWM(ctx context.Context, extra map[string]interface{}) (float64, error)

    // SetPWM sets the pin to the given duty cycle (0.0 to 1.0).
    SetPWM(ctx context.Context, dutyCyclePct float64,
        extra map[string]interface{}) error

    // PWMFreq gets the PWM frequency of the pin in Hz.
    PWMFreq(ctx context.Context, extra map[string]interface{}) (uint, error)

    // SetPWMFreq sets the given pin to the given PWM frequency.
    // On Raspberry Pi, 0 uses a default of 800 Hz.
    SetPWMFreq(ctx context.Context, freqHz uint,
        extra map[string]interface{}) error
}
```

### Analog Sub-Interface

```go
type Analog interface {
    // Read reads the current analog value.
    Read(ctx context.Context, extra map[string]interface{}) (AnalogValue, error)

    // Write writes a value to the analog pin.
    Write(ctx context.Context, value int, extra map[string]interface{}) error
}

type AnalogValue struct {
    Value    int     // reading in bits
    Min      float32 // minimum raw value
    Max      float32 // maximum raw value
    StepSize float32 // precision per bit
}
```

### DigitalInterrupt Sub-Interface

```go
type DigitalInterrupt interface {
    // Name returns the name of the interrupt.
    Name() string

    // Value returns the current value of the interrupt (tick count).
    Value(ctx context.Context, extra map[string]interface{}) (int64, error)
}

type Tick struct {
    Name             string
    High             bool
    TimestampNanosec uint64  // relative only -- do not use as absolute timestamp
}
```

### PowerMode Values

```
pb.PowerMode_POWER_MODE_NORMAL
pb.PowerMode_POWER_MODE_OFFLINE_DEEP
```

### Helper Functions

```go
board.Named(name string) resource.Name
board.FromProvider(provider resource.Provider, name string) (Board, error)
board.NamesFromRobot(r robot.Robot) []string
board.ValidatePWMDutyCycle(dutyCyclePct float64) (float64, error)
```

---

## Motor

**Package:** `go.viam.com/rdk/components/motor`
**API string:** `rdk:component:motor`
**Protobuf:** `go.viam.com/api/component/motor/v1`

### Interface

```go
type Motor interface {
    resource.Resource
    resource.Actuator   // IsMoving, Stop

    // SetPower sets power percentage [-1.0, 1.0]. Negative = backward.
    SetPower(ctx context.Context, powerPct float64,
        extra map[string]interface{}) error

    // GoFor moves at rpm for the given number of revolutions.
    // Both rpm and revolutions can be negative. Blocks until done.
    GoFor(ctx context.Context, rpm, revolutions float64,
        extra map[string]interface{}) error

    // GoTo moves to an absolute position (in revolutions from zero) at the given RPM.
    // Blocks until done.
    GoTo(ctx context.Context, rpm, positionRevolutions float64,
        extra map[string]interface{}) error

    // SetRPM runs the motor at the specified RPM indefinitely.
    SetRPM(ctx context.Context, rpm float64,
        extra map[string]interface{}) error

    // ResetZeroPosition sets the current position (+/- offset) as the new zero.
    ResetZeroPosition(ctx context.Context, offset float64,
        extra map[string]interface{}) error

    // Position returns position in revolutions.
    Position(ctx context.Context, extra map[string]interface{}) (float64, error)

    // Properties returns whether the motor supports position reporting.
    Properties(ctx context.Context, extra map[string]interface{}) (Properties, error)

    // IsPowered returns (isOn, powerPct, error).
    IsPowered(ctx context.Context, extra map[string]interface{}) (bool, float64, error)
}
```

### Properties Struct

```go
type Properties struct {
    PositionReporting bool
}
```

### Utility Functions

```go
motor.Named(name string) resource.Name
motor.FromProvider(provider resource.Provider, name string) (Motor, error)
motor.NamesFromRobot(r robot.Robot) []string
motor.CheckSpeed(rpm, max float64) (string, error)   // warns if near 0 or max
motor.CheckRevolutions(revs float64) error            // errors if zero
motor.ClampPower(pwr float64) float64                 // clamps to [-1.0, 1.0]
motor.GetRequestedDirection(rpm, revolutions float64) float64
motor.GetSign(x float64) float64
```

---

## Servo

**Package:** `go.viam.com/rdk/components/servo`
**API string:** `rdk:component:servo`

### Interface

```go
type Servo interface {
    resource.Resource
    resource.Actuator   // IsMoving, Stop

    // Move moves the servo to the given angle (0-180 degrees).
    // Blocks until done.
    Move(ctx context.Context, angleDeg uint32,
        extra map[string]interface{}) error

    // Position returns the current set angle in degrees.
    Position(ctx context.Context, extra map[string]interface{}) (uint32, error)
}
```

---

## Sensor

**Package:** `go.viam.com/rdk/components/sensor`
**API string:** `rdk:component:sensor`

### Interface

```go
type Sensor interface {
    resource.Resource
    resource.Sensor   // Readings(ctx, extra) (map[string]interface{}, error)
}
```

A generic sensor that returns arbitrary key-value readings. For specialized
measurements (voltage, GPS, etc.), use the specific component types below.

---

## Movement Sensor

**Package:** `go.viam.com/rdk/components/movementsensor`
**API string:** `rdk:component:movement_sensor`

### Interface

```go
type MovementSensor interface {
    resource.Sensor     // Readings(ctx, extra) -- returns all supported measurements
    resource.Resource

    // Position returns (lat/long, altitude_meters, error).
    // Supported by GPS models.
    Position(ctx context.Context, extra map[string]interface{}) (*geo.Point, float64, error)

    // LinearVelocity returns velocity in m/s as a 3D vector.
    LinearVelocity(ctx context.Context, extra map[string]interface{}) (r3.Vector, error)

    // AngularVelocity returns angular velocity in deg/s.
    AngularVelocity(ctx context.Context,
        extra map[string]interface{}) (spatialmath.AngularVelocity, error)

    // LinearAcceleration returns acceleration in m/s^2.
    LinearAcceleration(ctx context.Context,
        extra map[string]interface{}) (r3.Vector, error)

    // CompassHeading returns heading in degrees [0, 360).
    CompassHeading(ctx context.Context, extra map[string]interface{}) (float64, error)

    // Orientation returns the current orientation.
    Orientation(ctx context.Context,
        extra map[string]interface{}) (spatialmath.Orientation, error)

    // Properties returns which measurements this sensor supports.
    Properties(ctx context.Context, extra map[string]interface{}) (*Properties, error)

    // Accuracy returns reliability metrics of the sensor.
    Accuracy(ctx context.Context, extra map[string]interface{}) (*Accuracy, error)
}
```

### Properties Struct

```go
type Properties struct {
    PositionSupported           bool
    OrientationSupported        bool
    CompassHeadingSupported     bool
    LinearVelocitySupported     bool
    AngularVelocitySupported    bool
    LinearAccelerationSupported bool
}
```

### Accuracy Struct

```go
type Accuracy struct {
    AccuracyMap        map[string]float32
    Hdop               float32   // horizontal dilution of precision
    Vdop               float32   // vertical dilution of precision
    NmeaFix            int32     // NMEA fix quality (-1 = invalid)
    CompassDegreeError float32
}
```

### Unit Conventions

| Measurement | Unit |
|------------|------|
| Position | lat/long degrees, altitude in meters |
| Linear velocity | m/s |
| Angular velocity | deg/s |
| Linear acceleration | m/s^2 |
| Compass heading | degrees [0, 360) |

### Helper Functions

```go
movementsensor.Named(name string) resource.Name
movementsensor.FromProvider(provider resource.Provider, name string) (MovementSensor, error)
movementsensor.DefaultAPIReadings(ctx, sensor, extra) (map[string]interface{}, error)
movementsensor.UnimplementedOptionalAccuracies() *Accuracy  // NaN values for unimplemented
```

---

## Encoder

**Package:** `go.viam.com/rdk/components/encoder`
**API string:** `rdk:component:encoder`

### Interface

```go
type Encoder interface {
    resource.Resource

    // Position returns (value, positionType, error).
    // positionType specifies whether returned as ticks or degrees.
    Position(ctx context.Context, positionType PositionType,
        extra map[string]interface{}) (float64, PositionType, error)

    // ResetPosition sets current position as the new zero.
    ResetPosition(ctx context.Context, extra map[string]interface{}) error

    // Properties returns which position types are supported.
    Properties(ctx context.Context, extra map[string]interface{}) (Properties, error)
}
```

### PositionType Enum

```go
type PositionType byte

const (
    PositionTypeUnspecified PositionType = iota
    PositionTypeTicks       // relative encoder
    PositionTypeDegrees     // absolute encoder
)
```

### Properties Struct

```go
type Properties struct {
    TicksCountSupported   bool
    AngleDegreesSupported bool
}
```

---

## Gripper

**Package:** `go.viam.com/rdk/components/gripper`
**API string:** `rdk:component:gripper`

### Interface

```go
type Gripper interface {
    resource.Resource
    resource.Shaped          // Geometries
    resource.Actuator        // IsMoving, Stop
    framesystem.InputEnabled // Kinematics, CurrentInputs, GoToInputs

    // Open opens the gripper. Blocks until done.
    Open(ctx context.Context, extra map[string]interface{}) error

    // Grab makes the gripper grab. Returns true if something was grabbed.
    // Blocks until done.
    Grab(ctx context.Context, extra map[string]interface{}) (bool, error)

    // IsHoldingSomething returns whether the gripper is currently holding an object.
    IsHoldingSomething(ctx context.Context,
        extra map[string]interface{}) (HoldingStatus, error)
}

type HoldingStatus struct {
    IsHoldingSomething bool
    Meta               map[string]interface{}
}
```

---

## Gantry

**Package:** `go.viam.com/rdk/components/gantry`
**API string:** `rdk:component:gantry`

### Interface

```go
type Gantry interface {
    resource.Resource
    resource.Shaped          // Geometries
    resource.Actuator        // IsMoving, Stop
    framesystem.InputEnabled // Kinematics, CurrentInputs, GoToInputs

    // Position returns current positions per axis in mm.
    Position(ctx context.Context, extra map[string]interface{}) ([]float64, error)

    // MoveToPosition moves to the specified positions (mm) at given speeds (mm/s).
    // Blocks until done.
    MoveToPosition(ctx context.Context, positionsMm, speedsMmPerSec []float64,
        extra map[string]interface{}) error

    // Lengths returns the length of each axis in mm.
    Lengths(ctx context.Context, extra map[string]interface{}) ([]float64, error)

    // Home runs the homing sequence. Returns true on success.
    Home(ctx context.Context, extra map[string]interface{}) (bool, error)
}
```

---

## Input Controller

**Package:** `go.viam.com/rdk/components/input`
**API string:** `rdk:component:input_controller`

### Controller Interface

```go
type Controller interface {
    resource.Resource

    // Controls returns the list of Controls provided by this controller.
    Controls(ctx context.Context, extra map[string]interface{}) ([]Control, error)

    // Events returns the most recent Event for each Control (current state).
    Events(ctx context.Context,
        extra map[string]interface{}) (map[Control]Event, error)

    // RegisterControlCallback registers a callback for specific EventTypes on a Control.
    // Callback runs on the firer's goroutine -- start a goroutine for long operations.
    RegisterControlCallback(ctx context.Context, control Control,
        triggers []EventType, ctrlFunc ControlFunction,
        extra map[string]interface{}) error
}

type ControlFunction func(ctx context.Context, ev Event)
```

### Event Types

```go
type EventType string

const (
    AllEvents         EventType = "AllEvents"          // additive to other callbacks
    Connect           EventType = "Connect"            // on init/reconnect
    Disconnect        EventType = "Disconnect"         // on unplug/timeout
    ButtonPress       EventType = "ButtonPress"
    ButtonRelease     EventType = "ButtonRelease"
    ButtonHold        EventType = "ButtonHold"         // repeated
    ButtonChange      EventType = "ButtonChange"       // up+down convenience
    PositionChangeAbs EventType = "PositionChangeAbs"  // joysticks
    PositionChangeRel EventType = "PositionChangeRel"  // mice
)
```

### Controls

```go
type Control string

// Axes
const (
    AbsoluteX, AbsoluteY, AbsoluteZ       Control = "AbsoluteX", ...
    AbsoluteRX, AbsoluteRY, AbsoluteRZ    Control = "AbsoluteRX", ...
    AbsoluteHat0X, AbsoluteHat0Y          Control = "AbsoluteHat0X", ...
)

// Buttons
const (
    ButtonSouth, ButtonEast, ButtonWest, ButtonNorth Control = ...
    ButtonLT, ButtonRT, ButtonLT2, ButtonRT2        Control = ...
    ButtonLThumb, ButtonRThumb                      Control = ...
    ButtonSelect, ButtonStart, ButtonMenu           Control = ...
    ButtonRecord, ButtonEStop                       Control = ...
)

// Pedals
const (
    AbsolutePedalAccelerator, AbsolutePedalBrake, AbsolutePedalClutch Control = ...
)
```

### Event Struct

```go
type Event struct {
    Time    time.Time
    Event   EventType
    Control Control    // which key/axis
    Value   float64    // 0 or 1 for buttons, -1.0 to +1.0 for axes
}
```

### Triggerable Interface (for injecting events)

```go
type Triggerable interface {
    TriggerEvent(ctx context.Context, event Event,
        extra map[string]interface{}) error
}
```

---

## Power Sensor

**Package:** `go.viam.com/rdk/components/powersensor`
**API string:** `rdk:component:power_sensor`

### Interface

```go
type PowerSensor interface {
    resource.Sensor     // Readings(ctx, extra)
    resource.Resource

    // Voltage returns (volts, isAC, error).
    Voltage(ctx context.Context, extra map[string]interface{}) (float64, bool, error)

    // Current returns (amps, isAC, error).
    Current(ctx context.Context, extra map[string]interface{}) (float64, bool, error)

    // Power returns watts.
    Power(ctx context.Context, extra map[string]interface{}) (float64, error)
}
```

### Unit Conventions

| Measurement | Unit |
|------------|------|
| Voltage | volts |
| Current | amperes |
| Power | watts |

---

## Audio Input

**Package:** `go.viam.com/rdk/components/audioin`
**API string:** `rdk:component:audio_in`

### Interface

```go
type AudioIn interface {
    resource.Resource

    // GetAudio starts streaming audio chunks.
    // codec: requested codec, durationSeconds: max duration,
    // previousTimestampNs: for continuation from a previous stream.
    // Returns a channel of AudioChunk.
    GetAudio(ctx context.Context, codec string, durationSeconds float32,
        previousTimestampNs int64,
        extra map[string]interface{}) (chan *AudioChunk, error)

    // Properties returns audio properties.
    Properties(ctx context.Context,
        extra map[string]interface{}) (utils.Properties, error)
}

type AudioChunk struct {
    AudioData                 []byte
    AudioInfo                 *utils.AudioInfo
    Sequence                  int32
    StartTimestampNanoseconds int64
    EndTimestampNanoseconds   int64
    RequestID                 string
}
```

---

## Audio Output

**Package:** `go.viam.com/rdk/components/audioout`
**API string:** `rdk:component:audio_out`

### Interface

```go
type AudioOut interface {
    resource.Resource

    // Play plays audio data.
    Play(ctx context.Context, data []byte, info *utils.AudioInfo,
        extra map[string]interface{}) error

    // Properties returns audio output properties.
    Properties(ctx context.Context,
        extra map[string]interface{}) (utils.Properties, error)
}
```

---

## Button

**Package:** `go.viam.com/rdk/components/button`
**API string:** `rdk:component:button`

### Interface

```go
type Button interface {
    resource.Resource

    // Push pushes the button.
    Push(ctx context.Context, extra map[string]interface{}) error
}
```

---

## Switch

**Package:** `go.viam.com/rdk/components/switch` (Go package: `toggleswitch`)
**API string:** `rdk:component:switch`

### Interface

```go
type Switch interface {
    resource.Resource

    // SetPosition sets the switch to the specified position.
    SetPosition(ctx context.Context, position uint32,
        extra map[string]interface{}) error

    // GetPosition returns the current position of the switch.
    GetPosition(ctx context.Context, extra map[string]interface{}) (uint32, error)

    // GetNumberOfPositions returns (count, labels, error).
    // Labels is nil/empty or has length == count.
    GetNumberOfPositions(ctx context.Context,
        extra map[string]interface{}) (uint32, []string, error)
}
```

**Note:** The Go package is named `toggleswitch` (not `switch`, which is a reserved keyword), but the API subtype string is `"switch"`.

---

## Pose Tracker

**Package:** `go.viam.com/rdk/components/posetracker`
**API string:** `rdk:component:pose_tracker`

### Interface

```go
type PoseTracker interface {
    resource.Resource

    // Poses returns the poses of the specified bodies (or all if empty).
    // Poses are in the PoseTracker's frame of reference.
    Poses(ctx context.Context, bodyNames []string,
        extra map[string]interface{}) (referenceframe.FrameSystemPoses, error)
}
```

---

## Generic Component

**Package:** `go.viam.com/rdk/components/generic`
**API string:** `rdk:component:generic`

No additional interface -- just `resource.Resource`. Used for components that
only need `DoCommand` for custom behavior.

```go
// The type parameter is resource.Resource, not a custom interface
generic.FromProvider(provider resource.Provider, name string) (resource.Resource, error)
```

---

## Navigation Service

**Package:** `go.viam.com/rdk/services/navigation`
**API string:** `rdk:service:navigation`

### Interface

```go
type Service interface {
    resource.Resource

    // Mode returns the current operating mode.
    Mode(ctx context.Context, extra map[string]interface{}) (Mode, error)

    // SetMode sets the operating mode.
    SetMode(ctx context.Context, mode Mode, extra map[string]interface{}) error

    // Location returns the current location as a GeoPose.
    Location(ctx context.Context,
        extra map[string]interface{}) (*spatialmath.GeoPose, error)

    // Waypoints returns unreached waypoints.
    Waypoints(ctx context.Context,
        extra map[string]interface{}) ([]Waypoint, error)

    // AddWaypoint adds a waypoint to storage.
    AddWaypoint(ctx context.Context, point *geo.Point,
        extra map[string]interface{}) error

    // RemoveWaypoint removes a waypoint by ID.
    // If the machine is navigating to it, motion is canceled.
    RemoveWaypoint(ctx context.Context, id primitive.ObjectID,
        extra map[string]interface{}) error

    // Obstacles returns transient and predefined obstacles.
    Obstacles(ctx context.Context,
        extra map[string]interface{}) ([]*spatialmath.GeoGeometry, error)

    // Paths returns planned paths (series of geo points) to waypoints.
    Paths(ctx context.Context, extra map[string]interface{}) ([]*Path, error)

    // Properties returns map type info for the configured service.
    Properties(ctx context.Context) (Properties, error)
}
```

### Mode Enum

```go
type Mode uint8

const (
    ModeManual   Mode = iota  // no autonomous navigation
    ModeWaypoint              // navigate through waypoints sequentially
    ModeExplore               // autonomous exploration
)
```

### MapType Enum

```go
type MapType uint8

const (
    NoMap  MapType = iota  // no map
    GPSMap                 // GPS-based map
)
```

### Supporting Types

```go
type Properties struct {
    MapType MapType
}

type Waypoint struct {
    ID      primitive.ObjectID
    Visited bool
    Order   int
    Lat     float64
    Long    float64
}

// ToPoint converts the waypoint to a *geo.Point
func (wp *Waypoint) ToPoint() *geo.Point

type Path struct {
    // unexported fields
    // Access via DestinationWaypointID() and GeoPoints()
}

func NewPath(id primitive.ObjectID, geoPoints []*geo.Point) (*Path, error)
```

### Usage Pattern

```go
navSvc, err := navigation.FromProvider(machine, "my_nav")

// Switch to waypoint mode
err = navSvc.SetMode(ctx, navigation.ModeWaypoint, nil)

// Add a waypoint
point := geo.NewPoint(40.7128, -74.0060)  // NYC
err = navSvc.AddWaypoint(ctx, point, nil)

// Check current location
loc, err := navSvc.Location(ctx, nil)

// List obstacles
obstacles, err := navSvc.Obstacles(ctx, nil)
```

---

## SLAM Service

**Package:** `go.viam.com/rdk/services/slam`
**API string:** `rdk:service:slam`

### Interface

```go
type Service interface {
    resource.Resource

    // Position returns the current pose in the SLAM map.
    Position(ctx context.Context) (spatialmath.Pose, error)

    // PointCloudMap returns a callback that streams PCD map data in chunks.
    // returnEditedMap: if true, returns the edited (corrected) map.
    PointCloudMap(ctx context.Context, returnEditedMap bool) (func() ([]byte, error), error)

    // InternalState returns a callback that streams the internal SLAM state.
    InternalState(ctx context.Context) (func() ([]byte, error), error)

    // Properties returns slam session properties.
    Properties(ctx context.Context) (Properties, error)
}
```

### Properties Struct

```go
type Properties struct {
    CloudSlam             bool        // running in the cloud?
    MappingMode           MappingMode
    InternalStateFileType string
    SensorInfo            []SensorInfo
}
```

### MappingMode Enum

```go
type MappingMode uint8

const (
    MappingModeNewMap             MappingMode = iota  // building a new map
    MappingModeLocalizationOnly                       // localizing on existing map
    MappingModeUpdateExistingMap                      // updating an existing map
)
```

### SensorInfo

```go
type SensorType uint8

const (
    SensorTypeCamera         SensorType = iota
    SensorTypeMovementSensor
)

type SensorInfo struct {
    Name string
    Type SensorType
}
```

### Helper Functions

```go
// Full-map convenience (concatenates streamed chunks)
slam.PointCloudMapFull(ctx, slamSvc, returnEditedMap) ([]byte, error)
slam.InternalStateFull(ctx, slamSvc) ([]byte, error)

// Get map bounds as Limits
slam.Limits(ctx, slamSvc, useEditedMap) ([]referenceframe.Limit, error)

// Generic chunk concatenation
slam.HelperConcatenateChunksToFull(f func() ([]byte, error)) ([]byte, error)
```

### Usage Pattern

```go
slamSvc, err := slam.FromProvider(machine, "my_slam")

// Get current position
pose, err := slamSvc.Position(ctx)

// Get full point cloud map as PCD bytes
pcdBytes, err := slam.PointCloudMapFull(ctx, slamSvc, true)

// Get SLAM properties
props, err := slamSvc.Properties(ctx)
```

---

## Data Manager Service

**Package:** `go.viam.com/rdk/services/datamanager`
**API string:** `rdk:service:data_manager`

### Interface

```go
type Service interface {
    resource.Resource

    // Sync triggers a sync of locally stored data to the cloud.
    Sync(ctx context.Context, extra map[string]interface{}) error

    // UploadBinaryDataToDatasets uploads raw binary data to specified datasets.
    UploadBinaryDataToDatasets(ctx context.Context, binaryData []byte,
        datasetIDs, tags []string, mimeType datasyncpb.MimeType,
        extra map[string]interface{}) error

    // UploadImageToDatasets uploads an image to specified datasets.
    UploadImageToDatasets(ctx context.Context, image image.Image,
        datasetIDs, tags []string, mimeType datasyncpb.MimeType,
        extra map[string]interface{}) error
}
```

### Data Capture Configuration

```go
type DataCaptureConfig struct {
    Name               resource.Name          `json:"name"`
    Method             string                 `json:"method"`
    CaptureFrequencyHz float32                `json:"capture_frequency_hz"`
    CaptureQueueSize   int                    `json:"capture_queue_size"`
    CaptureBufferSize  int                    `json:"capture_buffer_size"`
    AdditionalParams   map[string]interface{} `json:"additional_params"`
    Disabled           bool                   `json:"disabled"`
    Tags               []string               `json:"tags,omitempty"`
    CaptureDirectory   string                 `json:"capture_directory"`
}
```

### AssociatedConfig

```go
// Attached to resource configs via service_configs in robot JSON
type AssociatedConfig struct {
    CaptureMethods []DataCaptureConfig `json:"capture_methods"`
}
```

### CaptureConfigReading (dynamic capture control)

```go
type CaptureConfigReading struct {
    ResourceName       string   `json:"resource_name"`
    Method             string   `json:"method"`
    CaptureFrequencyHz *float32 `json:"capture_frequency_hz,omitempty"` // 0 disables capture
    Tags               []string `json:"tags"`
}
```

### Special Keys

```go
datamanager.ShouldSyncKey = "should_sync"  // sensor reading key to control sync
datamanager.CreateShouldSyncReading(toSync bool) map[string]interface{}
```

### Robot Config JSON Pattern

```json
{
  "name": "my_sensor",
  "api": "rdk:component:sensor",
  "model": "rdk:builtin:my_model",
  "service_configs": [
    {
      "type": "rdk:service:data_manager",
      "attributes": {
        "capture_methods": [
          {
            "method": "Readings",
            "capture_frequency_hz": 1.0,
            "disabled": false,
            "tags": ["env-data"]
          }
        ]
      }
    }
  ]
}
```

---

## Discovery Service

**Package:** `go.viam.com/rdk/services/discovery`
**API string:** `rdk:service:discovery`

### Interface

```go
type Service interface {
    resource.Resource

    // DiscoverResources returns configs for discovered resources.
    DiscoverResources(ctx context.Context,
        extra map[string]any) ([]resource.Config, error)
}
```

### Usage Pattern

```go
discoverySvc, err := discovery.FromProvider(machine, "my_discovery")

// Discover available resources
configs, err := discoverySvc.DiscoverResources(ctx, nil)
for _, cfg := range configs {
    fmt.Printf("Name: %s  Model: %s  API: %s\n", cfg.Name, cfg.Model, cfg.API)
}
```

---

## World State Store Service

**Package:** `go.viam.com/rdk/services/worldstatestore`
**API string:** `rdk:service:world_state_store`

### Interface

```go
type Service interface {
    resource.Resource

    // ListUUIDs returns all world state transform UUIDs.
    ListUUIDs(ctx context.Context, extra map[string]any) ([][]byte, error)

    // GetTransform returns a transform by UUID.
    GetTransform(ctx context.Context, uuid []byte,
        extra map[string]any) (*commonpb.Transform, error)

    // StreamTransformChanges returns a stream of transform changes.
    StreamTransformChanges(ctx context.Context,
        extra map[string]any) (*TransformChangeStream, error)
}
```

### Supporting Types

```go
type TransformChange struct {
    ChangeType    pb.TransformChangeType
    Transform     *commonpb.Transform
    UpdatedFields []string
}

type TransformChangeStream struct {
    // Call Next() repeatedly until io.EOF
}

func (s *TransformChangeStream) Next() (TransformChange, error)

func NewTransformChangeStreamFromChannel(ctx context.Context,
    ch <-chan TransformChange) *TransformChangeStream
```

---

## Base Remote Control Service

**Package:** `go.viam.com/rdk/services/baseremotecontrol`
**API string:** `rdk:service:base_remote_control`

### Interface

```go
type Service interface {
    resource.Resource

    // Close shuts down all remote control systems.
    Close(ctx context.Context) error

    // ControllerInputs returns the list of input controls being monitored.
    ControllerInputs() []input.Control
}
```

This service bridges an input controller to a base for remote driving. It
monitors specific controller inputs and translates them to base movement
commands.

---

## Generic Service

**Package:** `go.viam.com/rdk/services/generic`
**API string:** `rdk:service:generic`

No additional interface -- just `resource.Resource`. Used for services that only
need `DoCommand`.

```go
type Service interface {
    resource.Resource
}

generic.FromProvider(provider resource.Provider, name string) (resource.Resource, error)
```

---

## Common Integration Patterns

### Base + Movement Sensor (Autonomous Navigation)

```go
myBase, _ := base.FromProvider(machine, "my_base")
movSensor, _ := movementsensor.FromProvider(machine, "my_gps")

// Get current location
pos, alt, _ := movSensor.Position(ctx, nil)
heading, _ := movSensor.CompassHeading(ctx, nil)

// Drive toward target
myBase.Spin(ctx, targetAngle-heading, 45, nil)
myBase.MoveStraight(ctx, distanceMm, 200, nil)
```

### Input Controller + Base (Joystick Driving)

```go
controller, _ := input.FromProvider(machine, "my_gamepad")
myBase, _ := base.FromProvider(machine, "my_base")

controller.RegisterControlCallback(ctx, input.AbsoluteY,
    []input.EventType{input.PositionChangeAbs},
    func(ctx context.Context, ev input.Event) {
        // ev.Value is -1.0 to 1.0
        myBase.SetPower(ctx,
            r3.Vector{Y: ev.Value},    // forward/back
            r3.Vector{},               // no angular
            nil)
    }, nil)
```

### Motor + Encoder (Closed-Loop Control)

```go
myMotor, _ := motor.FromProvider(machine, "my_motor")
myEncoder, _ := encoder.FromProvider(machine, "my_encoder")

// Check encoder type
props, _ := myEncoder.Properties(ctx, nil)
if props.TicksCountSupported {
    pos, _, _ := myEncoder.Position(ctx, encoder.PositionTypeTicks, nil)
    fmt.Printf("Encoder ticks: %f\n", pos)
}

// Motor with built-in position reporting
motorProps, _ := myMotor.Properties(ctx, nil)
if motorProps.PositionReporting {
    myMotor.GoTo(ctx, 60, 10.0, nil) // go to 10 revolutions at 60 RPM
}
```

### Board GPIO + Motor (Low-Level Control)

```go
myBoard, _ := board.FromProvider(machine, "my_board")

// Read a limit switch
pin, _ := myBoard.GPIOPinByName("17")
isHigh, _ := pin.Get(ctx, nil)

// Read analog sensor
analog, _ := myBoard.AnalogByName("temperature")
reading, _ := analog.Read(ctx, nil)
fmt.Printf("ADC value: %d, step size: %f\n", reading.Value, reading.StepSize)

// Digital interrupt for wheel encoder
interrupt, _ := myBoard.DigitalInterruptByName("encoder_a")
tickCount, _ := interrupt.Value(ctx, nil)

// Stream interrupt ticks
ticksChan := make(chan board.Tick)
myBoard.StreamTicks(ctx, []board.DigitalInterrupt{interrupt}, ticksChan, nil)
go func() {
    for tick := range ticksChan {
        fmt.Printf("Tick on %s: high=%v\n", tick.Name, tick.High)
    }
}()
```

### Board PWM for Servo/LED Control

```go
myBoard, _ := board.FromProvider(machine, "my_board")
pin, _ := myBoard.GPIOPinByName("18")

// Set 50% duty cycle at 1000 Hz (LED dimming)
pin.SetPWMFreq(ctx, 1000, nil)
pin.SetPWM(ctx, 0.5, nil)
```

### Data Capture on Sensor

```go
// In robot config JSON, attach data capture to a sensor:
// "service_configs": [{"type": "rdk:service:data_manager", "attributes": {
//   "capture_methods": [{"method": "Readings", "capture_frequency_hz": 0.5}]
// }}]

// Programmatically trigger sync
dmSvc, _ := datamanager.FromProvider(machine, "builtin")
err := dmSvc.Sync(ctx, nil)
```

### SLAM + Navigation

```go
slamSvc, _ := slam.FromProvider(machine, "my_slam")
navSvc, _ := navigation.FromProvider(machine, "my_nav")

// Get current SLAM position
pose, _ := slamSvc.Position(ctx)

// Check nav mode
mode, _ := navSvc.Mode(ctx, nil)
if mode == navigation.ModeManual {
    navSvc.SetMode(ctx, navigation.ModeWaypoint, nil)
}

// Add waypoints for navigation
navSvc.AddWaypoint(ctx, geo.NewPoint(40.7128, -74.0060), nil)
```
