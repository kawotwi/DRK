# Viam C++ SDK Cheatsheet

---

## Component / Service Interface Quick Reference

| Type | Base Class | Key Methods |
|------|-----------|-------------|
| `Camera` | `Component` | `get_image()`, `get_images()`, `get_point_cloud()`, `get_properties()`, `get_geometries()`, `do_command()` |
| `Arm` | `Component`, `Stoppable` | `get_end_position()`, `move_to_position()`, `get_joint_positions()`, `move_to_joint_positions()`, `move_through_joint_positions()`, `is_moving()`, `get_kinematics()`, `get_3d_models()`, `stop()`, `do_command()` |
| `Sensor` | `Component` | `get_readings()`, `get_geometries()`, `do_command()` |
| `GenericComponent` | `Component` | `do_command()`, `get_geometries()` |
| `AudioIn` | `Component` | `get_audio()`, `get_properties()`, `get_geometries()`, `do_command()` |
| `AudioOut` | `Component` | `play()`, `get_properties()`, `get_geometries()`, `do_command()` |
| `Motor` | `Component`, `Stoppable` | `set_power()`, `go_for()`, `go_to()`, `get_position()`, `get_properties()`, `is_moving()`, `stop()` |
| `MLModelService` | `Service` | `infer()`, `metadata()` |
| `Discovery` | `Service` | `discover_resources()`, `do_command()` |
| `GenericService` | `Service` | `do_command()` |

**Mixins**: `Reconfigurable` (`reconfigure(deps, cfg)`), `Stoppable` (`stop(extra)`)

---

## Minimal Module Template

### CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.25 FATAL_ERROR)

project(my-module
    DESCRIPTION "My Viam C++ module"
    LANGUAGES CXX
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(viam-cpp-sdk REQUIRED)
find_package(Threads REQUIRED)

add_executable(my-module src/main.cpp src/my_component.cpp)
target_link_libraries(my-module
    PRIVATE viam-cpp-sdk::viamsdk Threads::Threads
)

install(TARGETS my-module DESTINATION .)
install(FILES meta.json DESTINATION .)
```

### src/my_component.hpp

```cpp
#pragma once

#include <viam/sdk/components/sensor.hpp>
#include <viam/sdk/config/resource.hpp>
#include <viam/sdk/resource/reconfigurable.hpp>

namespace vsdk = ::viam::sdk;

class MySensor final : public vsdk::Sensor, public vsdk::Reconfigurable {
public:
    MySensor(vsdk::Dependencies deps, vsdk::ResourceConfig cfg);
    ~MySensor() override = default;

    static std::vector<std::string> validate(vsdk::ResourceConfig cfg);

    void reconfigure(const vsdk::Dependencies& deps,
                     const vsdk::ResourceConfig& cfg) override;

    vsdk::ProtoStruct get_readings(const vsdk::ProtoStruct& extra) override;
    std::vector<vsdk::GeometryConfig> get_geometries(const vsdk::ProtoStruct& extra) override;
    vsdk::ProtoStruct do_command(const vsdk::ProtoStruct& command) override;

    static inline vsdk::Model model{"acme", "sensor", "my-sensor"};
};
```

### src/my_component.cpp

```cpp
#include "my_component.hpp"
#include <viam/sdk/log/logging.hpp>

MySensor::MySensor(vsdk::Dependencies deps, vsdk::ResourceConfig cfg)
    : Sensor(cfg.name()) {
    auto attrs = cfg.attributes();
    // Parse config attributes here
    VIAM_RESOURCE_LOG(info) << "MySensor configured: " << cfg.name();
}

std::vector<std::string> MySensor::validate(vsdk::ResourceConfig cfg) {
    // Validate config, throw std::invalid_argument on errors
    return {};  // no implicit dependencies
}

void MySensor::reconfigure(const vsdk::Dependencies& deps,
                            const vsdk::ResourceConfig& cfg) {
    auto attrs = cfg.attributes();
    // Re-parse config, update internal state
    VIAM_RESOURCE_LOG(info) << "MySensor reconfigured";
}

vsdk::ProtoStruct MySensor::get_readings(const vsdk::ProtoStruct& extra) {
    vsdk::ProtoStruct readings;
    readings["temperature"] = 22.5;
    readings["humidity"] = 45.0;
    return readings;
}

std::vector<vsdk::GeometryConfig> MySensor::get_geometries(
    const vsdk::ProtoStruct& extra) {
    return {};
}

vsdk::ProtoStruct MySensor::do_command(const vsdk::ProtoStruct& command) {
    return {};
}
```

### src/main.cpp

```cpp
#include <viam/sdk/common/instance.hpp>
#include <viam/sdk/module/service.hpp>
#include "my_component.hpp"

namespace vsdk = ::viam::sdk;

int main(int argc, char** argv) {
    vsdk::Instance inst;

    std::vector<std::shared_ptr<vsdk::ModelRegistration>> registrations;
    registrations.push_back(std::make_shared<vsdk::ModelRegistration>(
        vsdk::API::get<vsdk::Sensor>(),
        MySensor::model,
        [](vsdk::Dependencies deps, vsdk::ResourceConfig cfg) {
            return std::make_unique<MySensor>(std::move(deps), std::move(cfg));
        },
        MySensor::validate));

    auto svc = std::make_shared<vsdk::ModuleService>(argc, argv, registrations);
    svc->serve();
    return EXIT_SUCCESS;
}
```

### meta.json

```json
{
  "module_id": "acme:my-module",
  "visibility": "public",
  "url": "https://github.com/acme/my-module",
  "description": "My custom sensor module",
  "models": [
    {
      "api": "rdk:component:sensor",
      "model": "acme:sensor:my-sensor"
    }
  ]
}
```

---

## Module Registration Boilerplate

### Single model (inline)

```cpp
auto reg = std::make_shared<vsdk::ModelRegistration>(
    vsdk::API::get<vsdk::Camera>(),
    vsdk::Model{"ns", "family", "name"},
    [](vsdk::Dependencies deps, vsdk::ResourceConfig cfg) {
        return std::make_unique<MyCamera>(std::move(deps), std::move(cfg));
    },
    MyCamera::validate  // optional
);
```

### Multiple models

```cpp
std::vector<std::shared_ptr<vsdk::ModelRegistration>> create_all_model_registrations() {
    std::vector<std::shared_ptr<vsdk::ModelRegistration>> regs;
    regs.push_back(std::make_shared<vsdk::ModelRegistration>(
        vsdk::API::get<vsdk::Camera>(), MyCam::model,
        [](vsdk::Dependencies d, vsdk::ResourceConfig c) {
            return std::make_unique<MyCam>(std::move(d), std::move(c));
        }, MyCam::validate));
    regs.push_back(std::make_shared<vsdk::ModelRegistration>(
        vsdk::API::get<vsdk::Discovery>(), MyDiscovery::model,
        [](vsdk::Dependencies d, vsdk::ResourceConfig c) {
            return std::make_unique<MyDiscovery>(std::move(d), std::move(c));
        }));
    return regs;
}
```

### With shared context (for hardware sharing)

```cpp
auto ctx = std::make_shared<HardwareContext>();
auto reg = std::make_shared<vsdk::ModelRegistration>(
    vsdk::API::get<vsdk::Camera>(), MyCam::model,
    [ctx](vsdk::Dependencies deps, vsdk::ResourceConfig cfg) {
        return std::make_unique<MyCam>(std::move(deps), std::move(cfg), ctx);
    }, MyCam::validate);
```

---

## Config Attribute Access Patterns

```cpp
auto attrs = cfg.attributes();

// String attribute:
std::string host = attrs.at("host").get_unchecked<std::string>();

// Optional string:
std::string serial;
if (attrs.count("serial_number")) {
    serial = attrs["serial_number"].get_unchecked<std::string>();
}

// Integer (arrives as double):
int width = static_cast<int>(attrs["width_px"].get_unchecked<double>());

// Boolean:
bool enabled = attrs["enable_streaming"].get_unchecked<bool>();

// List of strings:
auto& list = attrs["sensors"].get_unchecked<vsdk::ProtoList>();
for (auto& item : list) {
    std::string s = item.get_unchecked<std::string>();
}

// Nested struct:
auto& nested = attrs["advanced"].get_unchecked<vsdk::ProtoStruct>();
double val = nested["threshold"].get_unchecked<double>();
```

---

## Logging Quick Reference

```cpp
VIAM_SDK_LOG(info)      << "Module starting";       // global log
VIAM_SDK_LOG(debug)     << "Debug detail: " << x;
VIAM_SDK_LOG(error)     << "Something failed";

VIAM_RESOURCE_LOG(info)  << "Resource configured";    // resource log (in member fn)
VIAM_RESOURCE_LOG(warn)  << "Frame age: " << ms << "ms";
VIAM_RESOURCE_LOG(error) << "Error: " << e.what();
```

Levels: `trace` < `debug` < `info` < `warn` < `error` < `fatal`

---

## Build Commands

### With Conan (recommended for production)

```bash
# Install dependencies
conan install . --output-folder=build --build=missing

# Configure
cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake -DCMAKE_BUILD_TYPE=RelWithDebInfo

# Build
cmake --build .

# Package
cpack  # creates module.tar.gz
```

### Without Conan (system packages)

```bash
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build .
```

### Common CMake flags

```bash
-DCMAKE_BUILD_TYPE=RelWithDebInfo      # optimized + debug info (default, recommended)
-DCMAKE_BUILD_TYPE=Debug               # for development
-DCMAKE_CXX_STANDARD=17               # or 20 for UR-style modules
-DCMAKE_INSTALL_PREFIX=./install       # install location
-DBUILD_SHARED_LIBS=OFF                # static linking (common for modules)
```

---

## Common Compiler/Linker Errors and Fixes

### "undefined reference to `viam::sdk::...`"

**Cause**: Not linking `viam-cpp-sdk::viamsdk`.

**Fix**: Add to your `target_link_libraries`:
```cmake
target_link_libraries(my-target PRIVATE viam-cpp-sdk::viamsdk)
```

### "error: 'Instance' was not declared"

**Cause**: Missing include.

**Fix**: `#include <viam/sdk/common/instance.hpp>`

### "protobuf version mismatch" / "This program was compiled against a newer version of Protocol Buffers"

**Cause**: Your module links against a different protobuf version than the SDK.

**Fix**: Use Conan to pin versions, or ensure your `find_package(Protobuf)` finds
the same version the SDK was built against. The SDK requires protobuf >= 3.12.4.

### "multiple definition of `...`" with protobuf

**Cause**: Linking both SDK-generated and your own proto stubs.

**Fix**: Link `viam-cpp-sdk::viamapi` for proto stubs only once. If using
FetchContent, delete SDK's static proto gens:
```cmake
PATCH_COMMAND find ./src/viam/api -name "*.pb.h" -type f -exec rm {} +
```

### "error: 'shared_mutex' is not a member of 'std'"

**Cause**: Compiling with C++14 (SDK default) but using C++17 features.

**Fix**: Set `CMAKE_CXX_STANDARD` to 17 or 20 in your CMakeLists.txt.

### Linker errors on macOS with undefined `_OBJC_CLASS_$_...`

**Cause**: Missing framework linkage (e.g. CoreAudio for audio modules).

**Fix**: Link required Apple frameworks:
```cmake
if(APPLE)
    find_library(COREAUDIO CoreAudio REQUIRED)
    target_link_libraries(my-target PRIVATE ${COREAUDIO})
endif()
```

### "terminate called: gRPC server failed to bind"

**Cause**: Socket path already in use (stale socket from previous run).

**Fix**: This is typically managed by viam-server. For local testing, remove
the stale socket file before starting.

### Segfault on startup with "Instance not found"

**Cause**: `viam::sdk::Instance` was not created before SDK objects, or was
destroyed too early.

**Fix**: Create `Instance` as the first thing in `main()` and ensure it
outlives all SDK objects:
```cpp
int main(int argc, char** argv) {
    const viam::sdk::Instance inst;  // MUST be first
    // ... everything else ...
}
```

### "No matching function for call to 'get_unchecked<int>'"

**Cause**: JSON integers are stored as `double` in `ProtoValue`.

**Fix**: Use `get_unchecked<double>()` and cast:
```cpp
int val = static_cast<int>(attrs["count"].get_unchecked<double>());
```

---

## gRPC Patterns

### Module serves over Unix Domain Socket (UDS)

The socket path is passed as the first CLI argument by viam-server:
```
./my-module /tmp/viam-module-1234.sock
```

`ModuleService(argc, argv, registrations)` handles this automatically.

### Message size limit

Default gRPC max message size is ~4MB. For large payloads (point clouds):
- The Viam SDK increases this for module communication
- Still check: 32MB hard limit for point clouds in practice

### Concurrent requests

gRPC dispatches requests on a thread pool. Your component methods
**will** be called concurrently. Protect shared state with mutexes.

---

## Dependency Key

```
viam-cpp-sdk::viamsdk     -- Full SDK (link this in most cases)
viam-cpp-sdk::viamapi     -- Proto/gRPC stubs only
Threads::Threads          -- pthreads
Boost::headers            -- Boost header-only libs
Boost::log                -- Boost.Log (SDK uses internally)
xtensor                   -- Tensor library (for Camera depth_map, MLModel tensors)
```
