# Viam Go SDK -- Resource API Reference

Deep reference for the `resource` package: interfaces, lifecycle, registration,
config, dependency injection, and module development patterns. Built from
`viamrobotics/rdk/resource/` source, April 2026.

---

## Table of Contents

1. [Core Interfaces](#core-interfaces)
2. [API and Model Triplets](#api-and-model-triplets)
3. [Resource Name](#resource-name)
4. [Resource Lifecycle](#resource-lifecycle)
5. [API Registration](#api-registration)
6. [Model Registration](#model-registration)
7. [Config and Validation](#config-and-validation)
8. [Dependency Injection](#dependency-injection)
9. [Provider Pattern](#provider-pattern)
10. [Convenience Embeddings](#convenience-embeddings)
11. [Resource Graph Internals](#resource-graph-internals)
12. [Complete Module Development Recipe](#complete-module-development-recipe)

---

## Core Interfaces

### resource.Resource

The fundamental interface every component and service implements.

```go
type Resource interface {
    // Name returns the fully qualified resource name.
    Name() Name

    // Reconfigure must reconfigure the resource atomically and in place.
    // If this cannot be guaranteed, embed AlwaysRebuild instead.
    Reconfigure(ctx context.Context, deps Dependencies, conf Config) error

    // DoCommand sends/receives arbitrary data.
    DoCommand(ctx context.Context,
        cmd map[string]interface{}) (map[string]interface{}, error)

    // Status returns the current status as key-value pairs.
    Status(ctx context.Context) (map[string]interface{}, error)

    // Close must safely shut down the resource. Must be idempotent.
    Close(ctx context.Context) error
}
```

### resource.Sensor

```go
type Sensor interface {
    // Readings returns arbitrary key-value measurements.
    Readings(ctx context.Context,
        extra map[string]interface{}) (map[string]interface{}, error)
}
```

### resource.Actuator

```go
type Actuator interface {
    // IsMoving returns whether the resource is currently in motion.
    IsMoving(context.Context) (bool, error)

    // Stop stops all movement.
    Stop(context.Context, map[string]interface{}) error
}
```

### resource.Shaped

```go
type Shaped interface {
    // Geometries returns collision geometries for the resource.
    // Poses are relative to the resource's frame.
    Geometries(context.Context,
        map[string]interface{}) ([]spatialmath.Geometry, error)
}
```

### resource.Provider

```go
type Provider interface {
    // GetResource returns the Resource associated with the given name.
    GetResource(name Name) (Resource, error)
}
```

### Interface Composition in Components

| Component | Resource | Actuator | Shaped | Sensor | InputEnabled |
|-----------|----------|----------|--------|--------|-------------|
| Base | x | x | x | | |
| Motor | x | x | | | |
| Servo | x | x | | | |
| Sensor | x | | | x | |
| MovementSensor | x | | | x | |
| Encoder | x | | | | |
| Gripper | x | x | x | | x |
| Gantry | x | x | x | | x |
| Board | x | | | | |
| InputController | x | | | | |
| PowerSensor | x | | | x | |
| Button | x | | | | |
| Switch | x | | | | |
| PoseTracker | x | | | | |
| AudioIn | x | | | | |
| AudioOut | x | | | | |
| Generic | x | | | | |

---

## API and Model Triplets

### API (namespace:type:subtype)

Identifies a resource API -- e.g., `rdk:component:motor`.

```go
type API struct {
    Type        APIType
    SubtypeName string
}

type APIType struct {
    Namespace APINamespace
    Name      string       // "component" or "service"
}

type APINamespace string
```

#### Key Constants

```go
const (
    APINamespaceRDK         = APINamespace("rdk")
    APINamespaceRDKInternal = APINamespace("rdk-internal")
    APITypeServiceName      = "service"
    APITypeComponentName    = "component"
)
```

#### Constructors

```go
// Full explicit construction
api := resource.NewAPI("acme", "component", "gizmo")

// From namespace shortcuts
api := resource.APINamespaceRDK.WithComponentType("motor")
api := resource.APINamespaceRDK.WithServiceType("navigation")

// Parse from string
api, err := resource.NewAPIFromString("rdk:component:motor")
```

#### Methods

```go
api.IsComponent() bool
api.IsService() bool
api.String() string         // "rdk:component:motor"
api.Validate() error
```

### Model (namespace:family:name)

Identifies a specific implementation of an API -- e.g., `rdk:builtin:gpio`.

```go
type Model struct {
    Family ModelFamily
    Name   string
}

type ModelFamily struct {
    Namespace ModelNamespace
    Name      string
}

type ModelNamespace string
```

#### Key Constants

```go
const ModelNamespaceRDK = ModelNamespace("rdk")

var (
    DefaultModelFamily  = ModelNamespaceRDK.WithFamily("builtin")     // rdk:builtin
    DefaultServiceModel = DefaultModelFamily.WithModel("builtin")      // rdk:builtin:builtin
)
```

#### Constructors

```go
// Full explicit
model := resource.NewModel("acme", "demo", "mygizmo")

// From namespace chain
model := resource.ModelNamespace("acme").WithFamily("demo").WithModel("mygizmo")

// Parse from string (supports "rdk:builtin:gpio" or just "gpio" -> rdk:builtin:gpio)
model, err := resource.NewModelFromString("acme:demo:mygizmo")
```

### APIModel (tuple for registry lookup)

```go
type APIModel struct {
    API   API
    Model Model
}
```

---

## Resource Name

A `Name` uniquely identifies a resource instance. It combines an API, an
optional remote prefix, and the resource's short name.

```go
type Name struct {
    API    API
    Remote string  // empty for local resources
    Name   string
}
```

### Constructors

```go
// Standard construction
name := resource.NewName(api, "my_motor")

// From a fully qualified string: "rdk:component:motor/my_motor"
name, err := resource.NewFromString("rdk:component:motor/my_motor")

// Convenience per-component
name := motor.Named("my_motor")
```

### Key Methods

```go
name.String() string                    // "rdk:component:motor/my_motor"
name.ShortName() string                 // "my_motor" or "remote1:my_motor"
name.ContainsRemoteNames() bool
name.PrependRemote(remoteName string) Name
name.PopRemote() Name
name.AsNamed() Named                    // returns a minimal resource stub
name.Validate() error
```

---

## Resource Lifecycle

### Construction

Resources are constructed via their registered `Constructor` when the robot
starts up or when config changes trigger creation.

```go
// The constructor signature
type Create[ResourceT Resource] func(
    ctx context.Context,
    deps Dependencies,
    conf Config,
    logger logging.Logger,
) (ResourceT, error)
```

The resource manager calls the constructor with:
1. A context
2. All declared dependencies (resolved from the resource graph)
3. The resource's Config (with ConvertedAttributes already populated)
4. A logger scoped to the resource

### Reconfigure

When a resource's config changes, the resource manager calls `Reconfigure`
rather than destroying and rebuilding the resource. This allows hot-swapping
config without downtime.

```go
func (m *myMotor) Reconfigure(ctx context.Context, deps resource.Dependencies,
    conf resource.Config) error {
    newConf, err := resource.NativeConfig[*Config](conf)
    if err != nil {
        return err
    }
    m.mu.Lock()
    defer m.mu.Unlock()
    // Update internal state atomically
    m.maxRPM = newConf.MaxRPM
    // Re-resolve dependencies
    enc, err := encoder.FromDependencies(deps, newConf.EncoderName)
    if err != nil {
        return err
    }
    m.encoder = enc
    return nil
}
```

### Close

Called when a resource is removed from config or the robot is shutting down.
Must be idempotent.

```go
func (m *myMotor) Close(ctx context.Context) error {
    m.mu.Lock()
    defer m.mu.Unlock()
    if m.cancelFunc != nil {
        m.cancelFunc()
    }
    return m.conn.Close()
}
```

### Lifecycle Order

```
Config loaded
  -> Validate config (ConfigValidator.Validate)
  -> Resolve dependencies from resource graph
  -> If resource exists and config changed:
       -> Call Reconfigure (if it returns MustRebuildError, fall through to construct)
  -> If resource is new or must rebuild:
       -> Call Constructor
  -> Resource is now live in the graph

Config removed:
  -> Call Close on the resource
  -> Remove from resource graph
```

---

## API Registration

API registration declares a new resource type (component or service API). This
happens at package init time and tells the RDK how to serve it over gRPC.

```go
func init() {
    resource.RegisterAPI(API, resource.APIRegistration[MyComponent]{
        // Constructor for the gRPC server that serves this API
        RPCServiceServerConstructor: NewRPCServiceServer,

        // Handler for the gRPC gateway (REST/gRPC-Web)
        RPCServiceHandler: pb.RegisterMyComponentServiceHandlerFromEndpoint,

        // gRPC service descriptor
        RPCServiceDesc: &pb.MyComponentService_ServiceDesc,

        // Client constructor for connecting to a remote instance
        RPCClient: NewClientFromConn,

        // Optional: limit instances (e.g., data_manager uses DefaultMaxInstance=1)
        MaxInstance: 0,  // 0 = unlimited
    })
}
```

### APIRegistration Fields

```go
type APIRegistration[ResourceT Resource] struct {
    RPCServiceServerConstructor func(apiGetter APIResourceGetter[ResourceT],
        logger logging.Logger) any
    RPCServiceHandler           rpc.RegisterServiceHandlerFromEndpointFunc
    RPCServiceDesc              *grpc.ServiceDesc
    ReflectRPCServiceDesc       *desc.ServiceDescriptor  // auto-populated
    RPCClient                   CreateRPCClient[ResourceT]
    MaxInstance                 int
    MakeEmptyCollection         func() APIResourceCollection[Resource]
}
```

### With Associated Config (Data Manager Pattern)

```go
resource.RegisterAPIWithAssociation(
    API,
    resource.APIRegistration[Service]{...},
    resource.AssociatedConfigRegistration[*AssociatedConfig]{
        AttributeMapConverter: newAssociatedConfig,
    },
)
```

---

## Model Registration

Model registration declares a specific implementation of an API. This tells the
RDK how to construct instances of your model.

### RegisterComponent

```go
resource.RegisterComponent(
    motor.API,                              // which API this implements
    resource.NewModel("acme", "demo", "my-motor"),  // model triplet
    resource.Registration[motor.Motor, *Config]{
        Constructor: func(ctx context.Context, deps resource.Dependencies,
            conf resource.Config, logger logging.Logger) (motor.Motor, error) {
            newConf, err := resource.NativeConfig[*Config](conf)
            if err != nil {
                return nil, err
            }
            return newMyMotor(ctx, deps, newConf, logger)
        },
        // Optional: provide a custom attribute converter
        // If omitted and Config is not NoNativeConfig, one is generated automatically
        // via TransformAttributeMap
        AttributeMapConverter: nil,
    },
)
```

### RegisterService

```go
resource.RegisterService(
    navigation.API,
    resource.NewModel("acme", "demo", "my-nav"),
    resource.Registration[navigation.Service, *Config]{
        Constructor: newMyNav,
    },
)
```

### RegisterDefaultService

For services that should always exist (like the builtin data manager):

```go
resource.RegisterDefaultService(
    datamanager.API,
    resource.DefaultServiceModel,
    resource.Registration[datamanager.Service, *Config]{
        Constructor: newBuiltinDataManager,
    },
)
```

### Registration Fields

```go
type Registration[ResourceT Resource, ConfigT any] struct {
    // Required: exactly one of Constructor or DeprecatedRobotConstructor
    Constructor Create[ResourceT]

    // Optional: converts raw attributes to your config type.
    // If nil and ConfigT is not NoNativeConfig, auto-generated via mapstructure.
    AttributeMapConverter AttributeMapConverter[ConfigT]

    // Deprecated: constructor that receives the whole robot
    DeprecatedRobotConstructor DeprecatedCreateWithRobot[ResourceT]

    // Experimental: weak dependencies found via matchers
    WeakDependencies []Matcher
}
```

### Lookup

```go
reg, ok := resource.LookupRegistration(api, model)
apiReg, ok := resource.LookupGenericAPIRegistration(api)
```

---

## Config and Validation

### Config Struct

```go
type Config struct {
    Name             string
    API              API
    Model            Model
    Frame            *referenceframe.LinkConfig     // optional frame config
    DependsOn        []string                       // explicit dependencies
    LogConfiguration *LogConfig                     // optional log level
    Attributes       utils.AttributeMap             // raw JSON attributes

    // Set by the framework:
    AssociatedResourceConfigs []AssociatedResourceConfig
    AssociatedAttributes      map[Name]AssociatedConfig
    ConvertedAttributes       ConfigValidator            // your parsed config
    ImplicitDependsOn         []string                   // from Validate()
    ImplicitOptionalDependsOn []string                   // from Validate()
}
```

### NativeConfig

Extract your typed config from the generic Config:

```go
func (m *myMotor) Reconfigure(ctx context.Context, deps resource.Dependencies,
    conf resource.Config) error {
    // Type-safe extraction of your config struct
    newConf, err := resource.NativeConfig[*MyConfig](conf)
    if err != nil {
        return err
    }
    // newConf is *MyConfig
    ...
}
```

### ConfigValidator Interface

Your config struct should implement this to declare required and optional
dependencies and validate fields:

```go
type ConfigValidator interface {
    Validate(path string) (requiredDependencies, optionalDependencies []string, err error)
}
```

Example:

```go
type Config struct {
    BoardName    string `json:"board"`
    Pin          string `json:"pin"`
    MaxRPM       int    `json:"max_rpm"`
    EncoderName  string `json:"encoder,omitempty"`
}

func (c *Config) Validate(path string) ([]string, []string, error) {
    if c.BoardName == "" {
        return nil, nil, resource.NewConfigValidationFieldRequiredError(path, "board")
    }
    if c.Pin == "" {
        return nil, nil, resource.NewConfigValidationFieldRequiredError(path, "pin")
    }

    // Required dependencies -- must exist for this resource to be built
    required := []string{c.BoardName}

    // Optional dependencies -- nice to have, but resource works without them
    var optional []string
    if c.EncoderName != "" {
        optional = append(optional, c.EncoderName)
    }

    return required, optional, nil
}
```

### Convenience Config Types

```go
// Embeddable: config that does not need validation
type TriviallyValidateConfig struct{}

// Embeddable: resource with no meaningful config at all
type NoNativeConfig struct {
    TriviallyValidateConfig
}
```

### Config Helper Methods

```go
conf.ResourceName() Name        // resource.Name from this config
conf.Dependencies() []string    // union of DependsOn + ImplicitDependsOn
conf.Validate(path, defaultAPIType string) (required, optional []string, err error)
```

### Validation Error Helpers

```go
resource.NewConfigValidationError(path string, err error) error
resource.NewConfigValidationFieldRequiredError(path, field string) error
```

### TransformAttributeMap

If you don't provide a custom `AttributeMapConverter`, the framework uses
`TransformAttributeMap` to convert the raw `utils.AttributeMap` into your config
struct using `mapstructure` with `json` tags:

```go
func TransformAttributeMap[T any](attributes utils.AttributeMap) (T, error)
```

---

## Dependency Injection

### Declaring Dependencies

Dependencies are declared in two ways:

1. **Explicit:** `DependsOn` field in the resource config JSON
2. **Implicit:** Returned from `ConfigValidator.Validate()` (required and optional)

### Resolving Dependencies

In your constructor or Reconfigure:

```go
func newMyMotor(ctx context.Context, deps resource.Dependencies,
    conf resource.Config, logger logging.Logger) (motor.Motor, error) {

    newConf, _ := resource.NativeConfig[*Config](conf)

    // Get a typed dependency using the per-component FromProvider or FromDependencies
    myBoard, err := board.FromDependencies(deps, newConf.BoardName)
    // Note: FromDependencies is deprecated; in new code consider using the
    // provider pattern, but deps-based lookup still works in constructors.
    if err != nil {
        return nil, err
    }

    // Generic dependency lookup
    res, err := deps.Lookup(resource.NewName(someAPI, "some_name"))
    if err != nil {
        return nil, err
    }

    return &myMotor{board: myBoard, ...}, nil
}
```

### Dependencies Type

```go
type Dependencies map[Name]Resource

// Lookup searches by name, with fuzzy matching on remote names.
func (d Dependencies) Lookup(name Name) (Resource, error)

// GetResource implements Provider so Dependencies can be used as a Provider.
func (d Dependencies) GetResource(name Name) (Resource, error)
```

### Dependency Resolution Order

The resource graph resolves dependencies topologically:
1. Parse all configs
2. Run Validate on each to discover implicit dependencies
3. Build a DAG of dependencies
4. Construct/reconfigure resources in dependency order
5. If a dependency fails, dependents get a `DependencyNotReadyError`

---

## Provider Pattern

The `Provider` interface is the preferred way to look up resources:

```go
type Provider interface {
    GetResource(name Name) (Resource, error)
}
```

Both `Dependencies` and `robot.Robot` implement `Provider`. Each component
package provides a `FromProvider` helper:

```go
// Preferred pattern (works with both Robot and Dependencies)
myMotor, err := motor.FromProvider(provider, "my_motor")

// Deprecated patterns (still work but less flexible)
myMotor, err := motor.FromRobot(robot, "my_motor")
myMotor, err := motor.FromDependencies(deps, "my_motor")
```

### Generic Resource Lookup

```go
// Type-safe lookup from any Provider
res, err := resource.FromProvider[motor.Motor](provider, motor.Named("my_motor"))

// Type assertion on a generic Resource
typedRes, err := resource.AsType[motor.Motor](genericResource)
```

---

## Convenience Embeddings

### TriviallyReconfigurable

Embed when your resource ignores config changes (Reconfigure is a no-op):

```go
type mySimpleComponent struct {
    resource.TriviallyReconfigurable
    // ...
}
```

### TriviallyCloseable

Embed when your resource has no cleanup:

```go
type mySimpleComponent struct {
    resource.TriviallyCloseable
    // ...
}
```

### AlwaysRebuild

Embed when your resource cannot be reconfigured and must be destroyed and
rebuilt on any config change:

```go
type myComplexComponent struct {
    resource.AlwaysRebuild
    // ...
}
// Reconfigure() returns NewMustRebuildError, triggering Close + Constructor
```

### Named (via Name.AsNamed())

Get a minimal resource stub that satisfies the Named portion of Resource:

```go
named := resource.NewName(api, "my_thing").AsNamed()
// named implements Name(), DoCommand() (returns ErrDoUnimplemented), Status()
```

### NewCloseOnlyResource

For resources that only need a close function:

```go
res := resource.NewCloseOnlyResource(name, func(ctx context.Context) error {
    return conn.Close()
})
```

---

## Resource Graph Internals

The resource manager maintains a directed acyclic graph (DAG) of all resources.

### Graph Structure

- **Nodes:** Each resource is a node, keyed by `resource.Name`
- **Edges:** Dependencies create directed edges (A depends on B -> edge from A to B)
- **Lifecycle states:** Each node tracks its state (unconfigured, configuring, ready, removing, etc.)

### Key Files

- `resource/resource_graph.go` -- graph data structure
- `resource/graph_node.go` -- per-node lifecycle state machine

### What Happens on Config Change

1. New config is diffed against current config
2. Changed/added resources are identified
3. The graph is updated with new dependency edges
4. Resources are processed in topological order:
   - New resources: construct via Constructor
   - Changed resources: call Reconfigure (or rebuild if MustRebuildError)
   - Removed resources: call Close, remove from graph
5. Resources whose dependencies failed get `DependencyNotReadyError`

---

## Complete Module Development Recipe

This is the end-to-end pattern for building a Go module that registers a custom
component (e.g., a custom motor).

### 1. Define Your Config

```go
package mymotor

import "go.viam.com/rdk/resource"

type Config struct {
    BoardName string  `json:"board"`
    Pin       string  `json:"pin"`
    MaxRPM    float64 `json:"max_rpm"`
}

func (c *Config) Validate(path string) ([]string, []string, error) {
    if c.BoardName == "" {
        return nil, nil, resource.NewConfigValidationFieldRequiredError(path, "board")
    }
    if c.Pin == "" {
        return nil, nil, resource.NewConfigValidationFieldRequiredError(path, "pin")
    }
    return []string{c.BoardName}, nil, nil
}
```

### 2. Define Your Model and Register

```go
package mymotor

import (
    "go.viam.com/rdk/components/motor"
    "go.viam.com/rdk/resource"
)

var Model = resource.NewModel("acme", "demo", "my-motor")

func init() {
    resource.RegisterComponent(motor.API, Model, resource.Registration[motor.Motor, *Config]{
        Constructor: newMyMotor,
    })
}
```

### 3. Implement the Component

```go
package mymotor

import (
    "context"
    "sync"

    "go.viam.com/rdk/components/board"
    "go.viam.com/rdk/components/motor"
    "go.viam.com/rdk/logging"
    "go.viam.com/rdk/resource"
)

type myMotor struct {
    resource.AlwaysRebuild   // or implement Reconfigure yourself
    name   resource.Name
    board  board.Board
    pin    board.GPIOPin
    maxRPM float64
    mu     sync.Mutex
    logger logging.Logger
}

func newMyMotor(ctx context.Context, deps resource.Dependencies,
    conf resource.Config, logger logging.Logger) (motor.Motor, error) {

    newConf, err := resource.NativeConfig[*Config](conf)
    if err != nil {
        return nil, err
    }

    b, err := board.FromDependencies(deps, newConf.BoardName)
    if err != nil {
        return nil, err
    }

    pin, err := b.GPIOPinByName(newConf.Pin)
    if err != nil {
        return nil, err
    }

    return &myMotor{
        name:   conf.ResourceName(),
        board:  b,
        pin:    pin,
        maxRPM: newConf.MaxRPM,
        logger: logger,
    }, nil
}

func (m *myMotor) Name() resource.Name { return m.name }

func (m *myMotor) SetPower(ctx context.Context, powerPct float64,
    extra map[string]interface{}) error {
    m.mu.Lock()
    defer m.mu.Unlock()
    powerPct = motor.ClampPower(powerPct)
    return m.pin.SetPWM(ctx, powerPct, nil)
}

// ... implement remaining motor.Motor methods ...

func (m *myMotor) DoCommand(ctx context.Context,
    cmd map[string]interface{}) (map[string]interface{}, error) {
    return nil, resource.ErrDoUnimplemented
}

func (m *myMotor) Status(ctx context.Context) (map[string]interface{}, error) {
    return map[string]interface{}{}, nil
}

func (m *myMotor) Close(ctx context.Context) error {
    m.mu.Lock()
    defer m.mu.Unlock()
    return m.pin.Set(ctx, false, nil)
}
```

### 4. Create the Module Entry Point

```go
package main

import (
    "go.viam.com/rdk/module"
    "go.viam.com/rdk/resource"
    "go.viam.com/rdk/components/motor"

    mymotor "github.com/acme/my-motor"
)

func main() {
    module.ModularMain(
        resource.APIModel{API: motor.API, Model: mymotor.Model},
    )
}
```

### 5. Robot Config JSON

```json
{
  "modules": [
    {
      "name": "acme-motor",
      "executable_path": "/path/to/my-motor-binary",
      "type": "local"
    }
  ],
  "components": [
    {
      "name": "my_motor",
      "api": "rdk:component:motor",
      "model": "acme:demo:my-motor",
      "depends_on": ["my_board"],
      "attributes": {
        "board": "my_board",
        "pin": "15",
        "max_rpm": 100
      }
    }
  ]
}
```

### Key Patterns to Follow

1. **Always use `resource.NativeConfig[*YourConfig](conf)`** to extract typed config
2. **Always implement `ConfigValidator.Validate`** to declare dependencies and validate fields
3. **Use `sync.Mutex`** for thread safety -- resources are called concurrently
4. **Make `Close` idempotent** -- it may be called multiple times
5. **Return `resource.ErrDoUnimplemented`** from `DoCommand` if you don't need custom commands
6. **Use `resource.AlwaysRebuild`** if your resource cannot be hot-reconfigured
7. **Dependencies declared in `Validate`** are automatically resolved and passed to Constructor/Reconfigure
8. **Use `logging.Logger`** (not `log.Printf`) for structured, level-aware logging
