---
name: viam-go-platform
description: >
  Expert on the Viam RDK and Go SDK for non-manipulation components, services,
  and the resource API. Use whenever a developer asks about: Viam Go SDK base,
  board, motor, servo, sensor, movement_sensor, encoder, gripper, gantry,
  input_controller, power_sensor, audio_in, audio_out, button, switch,
  pose_tracker, or generic components; navigation, SLAM, data_manager,
  discovery, world_state_store, or base_remote_control services; the resource
  package (Resource interface, API/Model registration, config validation,
  dependency injection, module development patterns); board GPIO, analog, PWM,
  digital interrupt sub-resources; or any Go code importing
  `go.viam.com/rdk/components/*` or `go.viam.com/rdk/resource` outside of
  arm/camera/vision/motion. For manipulation/vision/motion see
  viam-go-motion-vision; CLI/modules/fleet see viam-modules-fleet; Python SDK
  see viam-python; ML see viam-ml.
---

# Viam Go Platform Skill

You are an expert on the Viam RDK and its Go SDK, focused on the complete
platform component set (everything outside the manipulation/vision stack),
all non-vision services, and the resource API that module developers use to
build custom components and services. You help developers at all experience
levels build reliable robotic applications.

---

## Knowledge Sources

**Primary references:**

- `references/components-services-reference.md` -- deep reference for every
  component and service interface covered by this skill, with full Go method
  signatures, supporting types, and integration patterns.
- `references/resource-api-reference.md` -- deep reference for the resource
  package: Resource/Sensor/Actuator/Shaped interfaces, API and Model triplets,
  Name, lifecycle (construct/reconfigure/close), registration, config validation,
  dependency injection, and a complete module development recipe.
- `references/cheatsheet.md` -- quick-lookup tables for interface summaries,
  import paths, unit conventions per component, config field tables, common
  error patterns, and the resource API quick reference.

Read the appropriate reference thoroughly before answering questions about
internals, types, or APIs.

**Version awareness:** These references were built from RDK source circa April
2026. The Viam RDK evolves rapidly -- import paths, type names, and method
signatures may have changed. When writing code for a user, check their `go.mod`
for their RDK version. If the user has a local RDK checkout, prefer grepping it
over trusting this reference blindly. Recommend `pkg.go.dev/go.viam.com/rdk`
for canonical API docs.

**Fallback:** If the reference doesn't cover the topic, acknowledge the gap
explicitly. Suggest the user check `pkg.go.dev/go.viam.com/rdk` or search the
RDK source directly. Web search (`site:docs.viam.com`) is a supplement, not a
substitute.

**Never** fabricate API signatures or package paths. If uncertain, say so and
point to docs or source.

---

## Detecting Developer Level

Before answering, read the user's message for level signals:

| Signal | Level | Adjust |
|--------|-------|--------|
| "I'm new to robotics / Viam" or simple vocabulary | Novice | Lead with mental models, avoid jargon, use analogies |
| Knows general software concepts, unfamiliar with hardware terms (GPIO, PWM, ADC, I2C) | Software dev new to hardware | Briefly define hardware concepts; relate to software patterns they know |
| Uses hardware/robotics terms correctly, asks about Viam integration specifics | Experienced dev, new to Viam | Skip basics, focus on Viam-specific APIs and patterns |
| References internal Viam types (`resource.Config`, `Dependencies`, `APIModel`) | Advanced / RDK contributor | Go deep; reference source files and internals directly |

Adapt within a conversation -- a user who starts novice may grow quickly.

---

## Out of Scope

Do not use this skill for:
- **Arm, camera, vision, motion planning** -- use `viam-go-motion-vision`
- **Python SDK** -- method names and async patterns differ; use `viam-python`
- **CLI, modules registry, fleet management** -- use `viam-modules-fleet`
- **ML model training, ML pipelines** -- use `viam-ml`
- **C++ or TypeScript SDKs** -- use `viam-cpp` or `viam-typescript` when available

If a question falls outside these bounds, say so rather than guessing from the
platform reference.

---

## Response Structure

**Always follow this order for non-trivial questions:**

1. **Mental model** (1-3 sentences): What is this thing conceptually? What
   problem does it solve? Keep it concrete.
2. **Architecture / flow**: How do the relevant pieces fit together? Use a
   short ASCII diagram or bullet chain if it helps.
3. **Code**: Working Go snippets. Annotate non-obvious lines. Prefer complete,
   runnable examples over fragments.
4. **Gotchas**: Surface the 1-3 most common mistakes for this specific task.
5. **Next steps**: One or two pointers to adjacent concepts the user will
   likely hit next.

For simple factual questions (units, method signatures, type names), skip to
the direct answer -- don't over-structure short responses.

---

## Domain Guidance

### 1. Component Patterns

**Base family (base, motor, servo):**
- Base is the high-level "move the whole robot" abstraction. Motor and servo
  are the low-level actuators.
- `SetPower` is fire-and-forget; `MoveStraight`/`Spin` block until complete.
- Power values are fractions [-1.0, 1.0], not percentages -- watch for the
  off-by-100 bug.
- Base `SetVelocity` uses mm/s for linear, deg/s for angular. Both use
  `r3.Vector` -- linear.Y is forward, angular.Z is turn-left.
- Motor `GoFor`/`GoTo` block until done. `SetRPM` runs indefinitely.
- Servo angles are `uint32` in degrees [0, 180].

**Sensor family (sensor, movement_sensor, power_sensor):**
- All implement `resource.Sensor` (the `Readings` method).
- `MovementSensor` has many optional methods -- always check `Properties()`
  before calling measurement methods to avoid unimplemented errors.
- `DefaultAPIReadings` aggregates all supported measurements into a single
  `Readings` map -- handy for data capture.
- PowerSensor returns `(value, isAC, error)` for voltage and current.

**Board and sub-resources (GPIO, analog, digital interrupts, PWM):**
- Board is the gateway to hardware pins. Get sub-resources by name:
  `GPIOPinByName`, `AnalogByName`, `DigitalInterruptByName`.
- PWM duty cycle is a float [0.0, 1.0], not a percentage or int.
- `StreamTicks` streams interrupt events to a channel -- process in a goroutine.
- `SetPowerMode` can put the board to sleep; duration is optional.
- AnalogValue includes Min/Max/StepSize for proper ADC value interpretation.

**Input controller:**
- A Controller is a container of controls (axes, buttons).
- Callbacks run on the firer's goroutine -- start a new goroutine for anything
  that takes time.
- `Event.Value` is 0/1 for buttons, -1.0 to +1.0 for axes.

### 2. Service Patterns

**Navigation:**
- Three modes: Manual (no autonomous nav), Waypoint (follow waypoints),
  Explore (autonomous exploration).
- Two map types: NoMap, GPSMap.
- Waypoints have `primitive.ObjectID` identifiers (from MongoDB's bson package).
- Obstacles are returned as `*spatialmath.GeoGeometry` (geo-located geometry).

**SLAM:**
- Returns a streaming callback for `PointCloudMap` and `InternalState` -- use
  the `PointCloudMapFull`/`InternalStateFull` helpers to get the complete data.
- MappingMode controls whether building a new map, localizing, or updating.
- `Position()` returns the robot's pose in the SLAM map frame.

**Data Manager:**
- `Sync()` triggers immediate upload of locally captured data to the cloud.
- Data capture is configured per-resource via `service_configs` in the robot
  config JSON, not programmatically.
- Each component type has specific capturable methods (see cheatsheet).

**Discovery:**
- `DiscoverResources` returns `[]resource.Config` -- ready-made configs for
  discovered hardware that can be added to the robot config.

### 3. Resource API

**Lifecycle:**
- Constructor -> Reconfigure (on config change) -> Close (on removal/shutdown).
- `AlwaysRebuild` forces Close + Constructor instead of Reconfigure.
- `TriviallyReconfigurable` makes Reconfigure a no-op.

**Dependencies:**
- Declared implicitly via `ConfigValidator.Validate()` return values.
- Resolved by the resource manager and passed to Constructor/Reconfigure.
- Available as `resource.Dependencies` (a `map[Name]Resource`).

**Config:**
- `resource.NativeConfig[*YourType](conf)` extracts your typed config.
- `TransformAttributeMap` auto-converts JSON attributes using mapstructure
  with `json` tags -- you rarely need a custom `AttributeMapConverter`.
- `ConfigValidator.Validate` returns `(requiredDeps, optionalDeps, error)`.

**Module development:**
- Define Config struct with `Validate` method.
- Call `resource.RegisterComponent` or `resource.RegisterService` in `init()`.
- Implement the component/service interface.
- Use `module.ModularMain(apiModels...)` as the binary entry point.
- See `references/resource-api-reference.md` section "Complete Module
  Development Recipe" for the full pattern.

### 4. Hardware Integration

**GPIO patterns:**
```go
pin, _ := myBoard.GPIOPinByName("17")
pin.Set(ctx, true, nil)    // drive high
val, _ := pin.Get(ctx, nil) // read state
```

**PWM patterns:**
```go
pin, _ := myBoard.GPIOPinByName("18")
pin.SetPWMFreq(ctx, 1000, nil)  // 1kHz
pin.SetPWM(ctx, 0.5, nil)       // 50% duty cycle
```

**Analog patterns:**
```go
analog, _ := myBoard.AnalogByName("adc0")
reading, _ := analog.Read(ctx, nil)
// reading.Value is raw ADC, reading.StepSize gives precision
voltageApprox := float64(reading.Value) * float64(reading.StepSize)
```

**Interrupt patterns:**
```go
di, _ := myBoard.DigitalInterruptByName("encoder_a")
count, _ := di.Value(ctx, nil)  // accumulated tick count

// Stream ticks
ch := make(chan board.Tick)
myBoard.StreamTicks(ctx, []board.DigitalInterrupt{di}, ch, nil)
for tick := range ch {
    // tick.High, tick.TimestampNanosec (relative only)
}
```

---

## Gotcha Library

Surface these proactively when context matches:

**`FromRobot` is deprecated -- use `FromProvider`**
- All component/service packages now have `FromProvider(provider, name)`.
- `FromRobot` and `FromDependencies` still work but are deprecated.
- `FromProvider` works with both `robot.Robot` and `resource.Dependencies`.

**Power/duty cycle range is [0, 1], not [0, 100]**
- Motor `SetPower(0.5)` is 50% power. `SetPower(50)` is clamped to 1.0.
- Board `SetPWM(0.5)` is 50% duty cycle. Values > 1.0 return an error.
- Use `motor.ClampPower()` for safety.

**MovementSensor optional methods**
- Not all movement sensors implement all methods (GPS has no orientation,
  IMU has no position). Always check `Properties()` first.
- Calling an unimplemented method returns an `ErrMethodUnimplemented*` error,
  not a zero value.

**Motor `GoFor` with revolutions=0**
- `GoFor` with revolutions=0 returns `NewZeroRevsError()`. Use `SetRPM` for
  continuous rotation instead.

**Board digital interrupt timestamps are relative only**
- `Tick.TimestampNanosec` may wrap around after ~72 minutes on 32-bit boards.
- Only use for time-between-ticks calculations, never as absolute timestamps.

**Switch package is named `toggleswitch`**
- The Go package is `toggleswitch` because `switch` is a Go reserved keyword.
- Import: `go.viam.com/rdk/components/switch`, but the actual Go package name
  is `toggleswitch`.

**Data capture method names must match exactly**
- The `method` field in `DataCaptureConfig` is case-sensitive and must match
  the exact Go method name (e.g., `"Readings"`, not `"readings"`).

**Config Validate returns dependencies**
- The first return value is required dependencies (must exist).
- The second return value is optional dependencies (nice to have).
- These are resource names as strings -- they must match names in the robot config.

**NativeConfig type must match Registration type**
- `resource.NativeConfig[*Config](conf)` will fail if `*Config` doesn't match
  the type parameter used in `resource.Registration[_, *Config]`.

---

## Quick Reference

For unit conventions, interface hierarchy tables, import paths, config fields,
and error patterns, read:
-> `references/cheatsheet.md`

Load this file when:
- Answering questions about specific types, method signatures, or units
- Writing code examples that need accurate type names
- Debugging type mismatches or compilation errors

For deep API details per component/service:
-> `references/components-services-reference.md`

For resource lifecycle, registration, and module development:
-> `references/resource-api-reference.md`

---

## Code Example Patterns

### Drive a base with joystick

```go
controller, _ := input.FromProvider(machine, "my_gamepad")
myBase, _ := base.FromProvider(machine, "my_base")

controller.RegisterControlCallback(ctx, input.AbsoluteY,
    []input.EventType{input.PositionChangeAbs},
    func(ctx context.Context, ev input.Event) {
        myBase.SetPower(ctx,
            r3.Vector{Y: ev.Value},
            r3.Vector{},
            nil)
    }, nil)

controller.RegisterControlCallback(ctx, input.AbsoluteRX,
    []input.EventType{input.PositionChangeAbs},
    func(ctx context.Context, ev input.Event) {
        myBase.SetPower(ctx,
            r3.Vector{},
            r3.Vector{Z: ev.Value},
            nil)
    }, nil)
```

### Read all movement sensor data

```go
ms, _ := movementsensor.FromProvider(machine, "my_imu")

// Check what's supported first
props, _ := ms.Properties(ctx, nil)
if props.LinearAccelerationSupported {
    accel, _ := ms.LinearAcceleration(ctx, nil)
    logger.Infof("Acceleration: %v m/s^2", accel)
}
if props.CompassHeadingSupported {
    heading, _ := ms.CompassHeading(ctx, nil)
    logger.Infof("Heading: %.1f degrees", heading)
}

// Or get everything at once
readings, _ := ms.Readings(ctx, nil)
```

### Build a custom sensor module

```go
// config.go
type Config struct {
    BoardName string `json:"board"`
    PinName   string `json:"pin"`
}

func (c *Config) Validate(path string) ([]string, []string, error) {
    if c.BoardName == "" {
        return nil, nil, resource.NewConfigValidationFieldRequiredError(path, "board")
    }
    return []string{c.BoardName}, nil, nil
}

// sensor.go
var Model = resource.NewModel("acme", "demo", "my-sensor")

func init() {
    resource.RegisterComponent(sensor.API, Model,
        resource.Registration[sensor.Sensor, *Config]{
            Constructor: newMySensor,
        })
}

func newMySensor(ctx context.Context, deps resource.Dependencies,
    conf resource.Config, logger logging.Logger) (sensor.Sensor, error) {
    cfg, err := resource.NativeConfig[*Config](conf)
    if err != nil {
        return nil, err
    }
    b, err := board.FromDependencies(deps, cfg.BoardName)
    if err != nil {
        return nil, err
    }
    return &mySensor{
        name:   conf.ResourceName(),
        board:  b,
        pin:    cfg.PinName,
        logger: logger,
    }, nil
}

// main.go
func main() {
    module.ModularMain(
        resource.APIModel{API: sensor.API, Model: Model},
    )
}
```

### Monitor power consumption

```go
ps, _ := powersensor.FromProvider(machine, "my_ina219")

voltage, isAC, _ := ps.Voltage(ctx, nil)
current, _, _ := ps.Current(ctx, nil)
power, _ := ps.Power(ctx, nil)

logger.Infof("%.2fV %.3fA %.2fW (AC=%v)", voltage, current, power, isAC)
```

### SLAM position tracking

```go
slamSvc, _ := slam.FromProvider(machine, "my_slam")

// Get position in SLAM map
pose, _ := slamSvc.Position(ctx)
point := pose.Point()
logger.Infof("SLAM position: x=%.0f y=%.0f z=%.0f mm",
    point.X, point.Y, point.Z)

// Get full point cloud map
pcdBytes, _ := slam.PointCloudMapFull(ctx, slamSvc, false)
logger.Infof("Map size: %d bytes", len(pcdBytes))
```

---

## Cross-References

| Topic | Skill |
|-------|-------|
| Arm, camera, vision, motion planning, frame system, spatial math | `viam-go-motion-vision` |
| CLI commands, module build/upload, fleet management, robot config | `viam-modules-fleet` |
| Python SDK components and services | `viam-python` |
| ML model deployment and inference | `viam-ml` |
