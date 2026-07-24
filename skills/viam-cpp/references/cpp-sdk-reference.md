# Viam C++ SDK Reference

> Built from `viam-cpp-sdk` v0.25.1 source, April 2026. Verify against your
> installed SDK version -- APIs evolve.

---

## 1. Architecture Overview

The Viam C++ SDK provides:

- **Component/Service base classes** -- abstract interfaces matching the Viam
  API (Camera, Arm, Sensor, MLModelService, etc.)
- **Module framework** -- `ModuleService` handles gRPC lifecycle, registration,
  config delivery, and signal management
- **Registry** -- singleton that maps `(API, Model)` pairs to factory functions
- **Proto/gRPC plumbing** -- generated stubs, proto-value wrappers, client/server
  pairs for every resource type

```
 viam-server (Go RDK)
       |  (gRPC over UDS)
       v
 ModuleService
   |- Registry  (API+Model -> factory)
   |- Server    (gRPC server, resource servers)
   |- Module    (socket addr, handler map)
   '- SignalManager (SIGINT/SIGTERM)
       |
       v
 Your Resource (Camera, Arm, MLModelService, ...)
   implements virtual methods
   receives Dependencies + ResourceConfig
```

### Class hierarchy

```
Resource (name, api(), logger_)
  +-- Component (get_resource_name with "rdk:component:" prefix)
  |     +-- Camera
  |     +-- Arm (also Stoppable)
  |     +-- Sensor
  |     +-- GenericComponent
  |     +-- AudioIn
  |     +-- AudioOut
  |     +-- Motor, Base, Board, Servo, Encoder, Gripper, Gantry, ...
  +-- Service (get_resource_name with "rdk:service:" prefix)
        +-- MLModelService
        +-- Discovery
        +-- Motion, Navigation, GenericService
```

### Mixins

| Mixin | Header | Purpose |
|-------|--------|---------|
| `Reconfigurable` | `resource/reconfigurable.hpp` | `reconfigure(deps, cfg)` -- called on config changes |
| `Stoppable` | `resource/stoppable.hpp` | `stop(extra)` -- called on shutdown |

Modules **should** implement `Reconfigurable` for live config updates without
restart. `Stoppable` is required for resources that hold hardware state (arms,
motors) and recommended for streaming resources (cameras).

---

## 2. Instance Lifecycle

Every C++ SDK program must create exactly one `viam::sdk::Instance` before
any other SDK objects. It initializes the global Registry, logging, and gRPC
infrastructure.

```cpp
#include <viam/sdk/common/instance.hpp>

int main(int argc, char** argv) {
    const viam::sdk::Instance inst;
    // ... create ModuleService, register models, serve ...
    return EXIT_SUCCESS;
}
```

The `Instance` must outlive all SDK objects. Destroying it tears down logging
and the registry.

---

## 3. Module Registration & Entry Point

### Pattern 1: Constructor with registrations vector (preferred, modern)

```cpp
#include <viam/sdk/common/instance.hpp>
#include <viam/sdk/module/service.hpp>

int main(int argc, char** argv) {
    viam::sdk::Instance inst;

    std::vector<std::shared_ptr<viam::sdk::ModelRegistration>> registrations;

    registrations.push_back(std::make_shared<viam::sdk::ModelRegistration>(
        viam::sdk::API::get<viam::sdk::Camera>(),      // API
        viam::sdk::Model{"acme", "camera", "mycam"},    // Model triple
        [](viam::sdk::Dependencies deps, viam::sdk::ResourceConfig cfg) {
            return std::make_unique<MyCam>(std::move(deps), std::move(cfg));
        },
        MyCam::validate  // optional validator
    ));

    auto svc = std::make_shared<viam::sdk::ModuleService>(
        argc, argv, registrations);
    svc->serve();  // blocks until SIGINT/SIGTERM

    return EXIT_SUCCESS;
}
```

`ModuleService(argc, argv, registrations)` parses the socket path and log
level from command-line args, registers all models, adds them, and is ready
to serve.

### Pattern 2: Manual registration + add_model_from_registry

Used by older modules (e.g. TFLite):

```cpp
viam::sdk::Instance inst;

auto reg = std::make_shared<viam::sdk::ModelRegistration>(
    viam::sdk::API::get<viam::sdk::MLModelService>(),
    viam::sdk::Model{"viam", "mlmodel-tflite", "tflite_cpu"},
    [](viam::sdk::Dependencies deps, viam::sdk::ResourceConfig cfg) {
        return std::make_shared<MLModelServiceTFLite>(
            std::move(deps), std::move(cfg));
    });

viam::sdk::Registry::get().register_model(reg);

auto svc = std::make_shared<viam::sdk::ModuleService>(socket_path);
svc->add_model_from_registry(reg->api(), reg->model());
svc->serve();
```

### Pattern 3: Static method returning registrations

Used by the UR arm -- clean separation:

```cpp
// In ur_arm.hpp:
static std::vector<std::shared_ptr<ModelRegistration>> create_model_registrations();

// In main.cpp:
const Instance instance;
std::make_shared<ModuleService>(
    argc, argv, URArm::create_model_registrations())->serve();
```

---

## 4. ModelRegistration

```cpp
class ModelRegistration {
public:
    ModelRegistration(
        API api,
        Model model,
        std::function<std::shared_ptr<Resource>(Dependencies, ResourceConfig)> constructor
    );

    ModelRegistration(
        API api,
        Model model,
        std::function<std::shared_ptr<Resource>(Dependencies, ResourceConfig)> constructor,
        std::function<std::vector<std::string>(ResourceConfig)> validator
    );
};
```

- **constructor**: Factory -- receives deps and config, returns the resource.
  Use `std::make_unique<T>(...)` (the unique_ptr implicitly converts to
  shared_ptr).
- **validator**: Called before construction. Throw `std::invalid_argument` on
  bad config. Return a `vector<string>` of implicit dependency names (usually
  empty `{}`).

---

## 5. ResourceConfig & Attributes

```cpp
class ResourceConfig {
public:
    const std::string& name() const;
    const std::string& namespace_() const;
    const std::string& type() const;
    const Model& model() const;
    const API& api() const;
    const ProtoStruct& attributes() const;  // <-- user config
    const std::vector<std::string>& depends_on() const;
    log_level get_log_level() const;
};
```

### Reading config attributes

Attributes are a `ProtoStruct` (= `std::unordered_map<std::string, ProtoValue>`).
ProtoValue can hold: `nullptr`, `bool`, `int` (stored as double), `double`,
`std::string`, `ProtoList` (= `std::vector<ProtoValue>`), or `ProtoStruct`.

```cpp
auto attrs = cfg.attributes();

// Check existence and type before reading:
if (attrs.count("host")) {
    if (!attrs["host"].is_a<std::string>()) {
        throw std::invalid_argument("host must be a string");
    }
    std::string host = attrs["host"].get_unchecked<std::string>();
}

// Numbers come as double -- cast to int if needed:
if (attrs.count("width_px")) {
    int width = static_cast<int>(attrs["width_px"].get_unchecked<double>());
}

// Lists:
if (attrs.count("sensors")) {
    auto& list = attrs["sensors"].get_unchecked<viam::sdk::ProtoList>();
    for (auto& item : list) {
        std::string s = item.get_unchecked<std::string>();
    }
}
```

**Key gotcha**: JSON integers arrive as `double`. Always use
`attrs[key].is_a<double>()` and cast, not `is_a<int>()`.

---

## 6. Dependencies

```cpp
using Dependencies = std::unordered_map<Name, std::shared_ptr<Resource>>;
```

Dependencies are other resources your resource depends on. Declared in config
via `depends_on` or returned from the validator. Access them by name:

```cpp
for (auto& [name, resource] : deps) {
    if (name.api() == API::get<Camera>()) {
        auto cam = std::dynamic_pointer_cast<Camera>(resource);
    }
}
```

---

## 7. API and Model Types

```cpp
// API = namespace:type:subtype  e.g. "rdk:component:camera"
class API {
    API(std::string ns, std::string resource_type, std::string resource_subtype);
    static API from_string(std::string api);
    template <typename T> static API get();  // uses API::traits<T>
};

// Model = namespace:family:name  e.g. "viam:camera:realsense"
class Model {
    Model(std::string namespace_, std::string family, std::string model_name);
    static Model from_str(std::string model);
};

// Name = API + remote_name + name
class Name {
    const API& api() const;
    const std::string& name() const;
};
```

Declare your model as a static member:

```cpp
static inline viam::sdk::Model model{"viam", "camera", "realsense"};
```

---

## 8. Component/Service Interface Signatures

### Camera (`components/camera.hpp`)

```cpp
class Camera : public Component {
    struct raw_image { std::string mime_type; std::vector<unsigned char> bytes; std::string source_name; };
    struct image_collection { std::vector<raw_image> images; response_metadata metadata; };
    struct point_cloud { std::string mime_type; std::vector<unsigned char> pc; };
    struct properties { bool supports_pcd; intrinsic_parameters; distortion_parameters; mime_types; float frame_rate; };
    using depth_map = xt::xarray<uint16_t>;

    virtual raw_image get_image(std::string mime_type, const ProtoStruct& extra) = 0;
    virtual image_collection get_images(std::vector<std::string> filter, const ProtoStruct& extra) = 0;
    virtual point_cloud get_point_cloud(std::string mime_type, const ProtoStruct& extra) = 0;
    virtual properties get_properties() = 0;
    virtual std::vector<GeometryConfig> get_geometries(const ProtoStruct& extra) = 0;
    virtual ProtoStruct do_command(const ProtoStruct& command) = 0;
};
```

### Arm (`components/arm.hpp`)

```cpp
class Arm : public Component, public Stoppable {
    virtual pose get_end_position(const ProtoStruct& extra) = 0;
    virtual void move_to_position(const pose& pose, const ProtoStruct& extra) = 0;
    virtual std::vector<double> get_joint_positions(const ProtoStruct& extra) = 0;
    virtual void move_to_joint_positions(const std::vector<double>& positions, const ProtoStruct& extra) = 0;
    virtual void move_through_joint_positions(const std::vector<std::vector<double>>& positions,
                                              const MoveOptions& options, const ProtoStruct& extra) = 0;
    virtual bool is_moving() = 0;
    virtual KinematicsData get_kinematics(const ProtoStruct& extra) = 0;
    virtual std::map<std::string, mesh> get_3d_models(const ProtoStruct& extra) = 0;
    virtual std::vector<GeometryConfig> get_geometries(const ProtoStruct& extra) = 0;
    virtual ProtoStruct do_command(const ProtoStruct& command) = 0;
    // from Stoppable:
    virtual void stop(const ProtoStruct& extra) = 0;
};
```

### Sensor (`components/sensor.hpp`)

```cpp
class Sensor : public Component {
    virtual ProtoStruct get_readings(const ProtoStruct& extra) = 0;
    virtual std::vector<GeometryConfig> get_geometries(const ProtoStruct& extra) = 0;
    virtual ProtoStruct do_command(const ProtoStruct& command) = 0;
};
```

### MLModelService (`services/mlmodel.hpp`)

```cpp
class MLModelService : public Service {
    using named_tensor_views = std::unordered_map<std::string, tensor_views>;
    // tensor_views = boost::variant over tensor_view<int8_t>, ..., tensor_view<double>
    // tensor_view<T> = xt::adapt(...) non-owning view

    virtual std::shared_ptr<named_tensor_views> infer(
        const named_tensor_views& inputs, const ProtoStruct& extra) = 0;

    virtual struct metadata metadata(const ProtoStruct& extra) = 0;
    // metadata includes: name, type, description, vector<tensor_info> inputs/outputs
};
```

### GenericComponent (`components/generic.hpp`)

```cpp
class GenericComponent : public Component {
    virtual ProtoStruct do_command(const ProtoStruct& command) = 0;
    virtual std::vector<GeometryConfig> get_geometries(const ProtoStruct& extra) = 0;
};
```

### Discovery (`services/discovery.hpp`)

```cpp
class Discovery : public Service {
    virtual std::vector<ResourceConfig> discover_resources(const ProtoStruct& extra) = 0;
    virtual ProtoStruct do_command(const ProtoStruct& command) = 0;
};
```

### AudioIn / AudioOut (`components/audio_in.hpp`, `components/audio_out.hpp`)

AudioIn provides streaming audio via `get_audio()`; AudioOut provides `play()`.

---

## 9. Logging

```cpp
#include <viam/sdk/log/logging.hpp>

// Global SDK log (not tied to a resource):
VIAM_SDK_LOG(info) << "Starting module";
VIAM_SDK_LOG(debug) << "Detail: " << value;

// Resource-level log (inside a Resource subclass member function):
VIAM_RESOURCE_LOG(info) << "Configuring device " << serial;
VIAM_RESOURCE_LOG(error) << "Failed: " << e.what();
```

Log levels: `trace`, `debug`, `info`, `warn`, `error`, `fatal`.

The log level is typically set from `--log-level=debug` passed by viam-server
on the command line. The SDK parses this automatically in `ModuleService`.

---

## 10. Error Handling

The SDK does **not** use `grpc::Status` directly in module code. Instead:

- **Throw exceptions** from your virtual method implementations. The SDK's
  gRPC server layer catches them and converts to gRPC status errors.
- Use `std::runtime_error` for operational errors.
- Use `std::invalid_argument` for config validation errors.
- The gRPC client layer converts status errors back to C++ exceptions.

```cpp
void move_to_position(const pose& p, const ProtoStruct&) override {
    if (!connected_) {
        throw std::runtime_error("arm is not connected");
    }
    // ...
}
```

---

## 11. Threading Model

- **gRPC threads**: The SDK's gRPC server dispatches calls on a thread pool.
  Multiple component methods can be called concurrently.
- **Component threads**: Modules often run background threads for streaming
  (cameras), control loops (arms), or audio callbacks. You manage these.
- **Synchronization**: Use `std::mutex`, `std::shared_mutex`, or
  `boost::synchronized_value` to protect shared state.

Key patterns from production modules:
- **RealSense**: Uses `boost::synchronized_value<T>` extensively for
  thread-safe access to device state, framesets, and config.
- **UR arm**: Uses `std::shared_mutex` with read locks for queries and
  write locks for config/state changes.
- **TFLite**: Uses `std::shared_mutex` (`state_rwmutex_`) so inference calls
  can run concurrently while reconfigure takes exclusive access.

---

## 12. Memory Management

- **RAII everywhere**: Use smart pointers. `std::make_unique` in factories,
  `std::shared_ptr` for shared state across threads.
- The SDK returns `std::shared_ptr<Resource>` from factories.
- Frame data, point clouds, and images are returned by value
  (`std::vector<unsigned char>`).
- **tensor_views are non-owning**: The `shared_ptr<named_tensor_views>`
  returned by `infer()` must remain alive while you access tensor data.
- **Destructor ordering**: Clean up hardware resources (stop streams, close
  connections) in your destructor. The SDK destructs resources before
  tearing down gRPC.

---

## 13. CMake Integration

### Finding the SDK (installed)

```cmake
find_package(viam-cpp-sdk REQUIRED)
# or with version:
find_package(viam-cpp-sdk 0.31 CONFIG REQUIRED viamsdk)

target_link_libraries(my-module
    PRIVATE viam-cpp-sdk::viamsdk
)
```

### FetchContent (pulling SDK at build time)

```cmake
include(FetchContent)
FetchContent_Declare(
    viam-cpp-sdk
    GIT_REPOSITORY https://github.com/viamrobotics/viam-cpp-sdk
    GIT_TAG releases/v0.31.0
    GIT_SHALLOW TRUE
    SYSTEM
    FIND_PACKAGE_ARGS
)
FetchContent_MakeAvailable(viam-cpp-sdk)
```

### Conan dependency management

Most production modules use Conan for dependency management:

```python
# conanfile.py
def requirements(self):
    self.requires("viam-cpp-sdk/0.31.0")
    self.requires("librealsense/2.56.5")  # etc.
```

### Key link targets

| Target | What it provides |
|--------|-----------------|
| `viam-cpp-sdk::viamsdk` | Full SDK (components, services, module, registry, gRPC) |
| `viam-cpp-sdk::viamapi` | Just the gRPC/protobuf API stubs |

### Required dependencies

The SDK itself requires:
- CMake >= 3.25
- C++14 (SDK default) or higher (C++17 or C++20 for modules)
- Boost >= 1.71 (headers, log, log_setup)
- gRPC >= 1.30.2
- Protobuf >= 3.12.4
- xtl >= 0.7.2, xtensor >= 0.24.3
- Threads (pthread)

---

## 14. ProtoStruct / ProtoValue Quick Reference

```cpp
// ProtoStruct = std::unordered_map<std::string, ProtoValue>
// ProtoList   = std::vector<ProtoValue>
// ProtoValue holds: nullptr, bool, double (int stored as double), string, ProtoList, ProtoStruct

ProtoValue val;
val.kind();                    // Kind enum: k_null, k_bool, k_double, k_string, k_list, k_struct
val.is_a<std::string>();       // type check
val.get<std::string>();        // returns pointer or nullptr
val.get_unchecked<double>();   // direct access, UB if wrong type

// Building responses:
ProtoStruct response;
response["success"] = true;
response["count"] = 42;        // stored as double
response["name"] = "test";
```

---

## 15. Common SDK Headers

```cpp
#include <viam/sdk/common/instance.hpp>       // Instance
#include <viam/sdk/module/service.hpp>         // ModuleService
#include <viam/sdk/registry/registry.hpp>      // Registry, ModelRegistration
#include <viam/sdk/config/resource.hpp>        // ResourceConfig
#include <viam/sdk/resource/resource.hpp>      // Resource, Dependencies
#include <viam/sdk/resource/reconfigurable.hpp>// Reconfigurable
#include <viam/sdk/resource/stoppable.hpp>     // Stoppable
#include <viam/sdk/log/logging.hpp>            // VIAM_SDK_LOG, VIAM_RESOURCE_LOG

// Components:
#include <viam/sdk/components/camera.hpp>
#include <viam/sdk/components/arm.hpp>
#include <viam/sdk/components/sensor.hpp>
#include <viam/sdk/components/generic.hpp>
#include <viam/sdk/components/audio_in.hpp>
#include <viam/sdk/components/audio_out.hpp>

// Services:
#include <viam/sdk/services/mlmodel.hpp>
#include <viam/sdk/services/discovery.hpp>
```
